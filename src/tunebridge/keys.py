"""Konten verbinden: API-Keys nach dem Login automatisch von der Dienst-Seite ablesen.

Ablauf (Desktop-App):
  1. Klick auf „Verbinden“ öffnet ein Fenster mit der echten Seite des Dienstes.
  2. Du loggst dich dort selbst ein – SH-Tunebridge sieht dein Passwort nie.
  3. SH-Tunebridge liest regelmäßig den sichtbaren Seitentext und erkennt die Keys
     an Beschriftung + Format, prüft sie beim Dienst und speichert sie.
Fallback (Browser-Modus oder wenn das Ablesen nicht klappt): Seite im Browser öffnen,
Key kopieren – SH-Tunebridge erkennt ihn in der Zwischenablage und fragt, ob er übernommen werden soll.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass, field

import httpx

from . import config


@dataclass
class Field:
    key: str                 # Name in config.env
    value_re: str            # Format des Werts
    label_re: str | None     # Beschriftung in der Nähe (None = Format reicht)


@dataclass
class Service:
    id: str
    name: str
    start_url: str
    pages_hint: str
    fields: list[Field] = field(default_factory=list)
    prefill: dict[str, str] = field(default_factory=dict)  # Formularvorbelegung (Feld-Hinweis -> Wert)


SERVICES: dict[str, Service] = {
    "lastfm": Service(
        "lastfm", "Last.fm", "https://www.last.fm/api/account/create",
        "Einloggen → Formular ist vorausgefüllt → E-Mail prüfen und absenden. Hast du schon eine App, öffne „API-Konten“.",
        [Field("LASTFM_API_KEY", r"\b[0-9a-f]{32}\b", r"api\s*key")],
        prefill={"name": "SH-Tunebridge", "description": "Persönliches Tool: Songs erkennen und nach Genre sortieren"},
    ),
    "audd": Service(
        "audd", "AudD", "https://dashboard.audd.io/",
        "Einloggen oder registrieren – der API-Token steht danach im Dashboard.",
        [Field("AUDD_API_TOKEN", r"\b[0-9a-f]{32}\b", r"token")],
    ),
    "acrcloud": Service(
        "acrcloud", "ACRCloud", "https://console.acrcloud.com/",
        "Einloggen → Audio & Video Recognition → Projekt öffnen (Bucket „ACRCloud Music“). Ggf. „Show“ beim Secret klicken.",
        [Field("ACRCLOUD_HOST", r"\bidentify-[a-z0-9-]+\.acrcloud\.com\b", None),
         Field("ACRCLOUD_ACCESS_KEY", r"\b[0-9a-f]{32}\b", r"access\s*key"),
         Field("ACRCLOUD_ACCESS_SECRET", r"\b[A-Za-z0-9]{40}\b", r"(access\s*)?secret")],
    ),
}

# JS: sichtbarer Text + Werte aus Eingabefeldern (mit ihrer Beschriftung) – nur lesen
EXTRACT_JS = r"""
(() => {
  const out = [document.body ? document.body.innerText : ""];
  document.querySelectorAll("input, textarea").forEach(el => {
    if (!el.value || el.type === "password" || el.type === "hidden") return;
    const lab = (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute("aria-label")
      || el.placeholder || el.name || el.id || (el.previousElementSibling && el.previousElementSibling.innerText) || "";
    out.push(lab + ": " + el.value);
  });
  return out.join("\n");
})()
"""

PREFILL_JS = r"""
((vals) => {
  const set = (el, v) => { if (!el || el.value) return;
    const p = Object.getOwnPropertyDescriptor(el.__proto__, "value"); p.set.call(el, v);
    el.dispatchEvent(new Event("input", {bubbles: true})); el.dispatchEvent(new Event("change", {bubbles: true})); };
  document.querySelectorAll("form input[type=text], form textarea").forEach(el => {
    const hint = ((el.labels && el.labels[0] && el.labels[0].innerText) || "") + " " + el.name + " " + el.id;
    if (/descr/i.test(hint)) set(el, vals.description);
    else if (/(app|application).*name|^\s*name|\bname\b/i.test(hint) && !/user|contact|mail/i.test(hint)) set(el, vals.name);
  });
  return true;
})
"""


def extract(service: Service, text: str) -> dict[str, str]:
    """Findet Werte anhand von Format und Beschriftung (gleiche oder bis zu 2 Zeilen davor)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    found: dict[str, str] = {}
    for f in service.fields:
        for i, line in enumerate(lines):
            for m in re.finditer(f.value_re, line):
                ctx = " ".join(lines[max(0, i - 2): i + 1])
                if f.label_re is None or re.search(f.label_re, ctx, re.I):
                    # Gleicher Wert darf nicht für zwei Felder herhalten
                    if m.group(0) not in found.values():
                        found.setdefault(f.key, m.group(0))
                    break
            if f.key in found:
                break
    return found


# ------------------------------------------------------------------ Prüfen
def _silent_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 8000)
    return buf.getvalue()


def validate(service_id: str, values: dict[str, str]) -> tuple[bool | None, str]:
    """(gültig?, Meldung) – None = konnte nicht geprüft werden."""
    try:
        if service_id == "lastfm":
            r = httpx.get("https://ws.audioscrobbler.com/2.0/", timeout=10, params={
                "method": "chart.gettopartists", "limit": 1, "format": "json", "api_key": values["LASTFM_API_KEY"]}).json()
            return (False, "Last.fm lehnt den Key ab") if r.get("error") in (10, 26) else (True, "Key funktioniert")
        if service_id == "audd":
            r = httpx.post("https://api.audd.io/", timeout=15, data={"api_token": values["AUDD_API_TOKEN"]}).json()
            if (r.get("error") or {}).get("error_code") == 900:
                return False, "AudD lehnt den Token ab"
            return True, "Token funktioniert"
        if service_id == "acrcloud":
            import base64, hashlib, hmac, time
            host, key, secret = (values.get(k) for k in ("ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET"))
            if not (host and key and secret):
                return None, "Noch nicht vollständig (Host, Key und Secret nötig)"
            ts = str(int(time.time()))
            sig = base64.b64encode(hmac.new(secret.encode(), "\n".join(
                ["POST", "/v1/identify", key, "audio", "1", ts]).encode(), hashlib.sha1).digest()).decode()
            data = _silent_wav()
            r = httpx.post(f"https://{host}/v1/identify", timeout=15, files={"sample": ("s.wav", data)}, data={
                "access_key": key, "sample_bytes": str(len(data)), "timestamp": ts, "signature": sig,
                "data_type": "audio", "signature_version": "1"}).json()
            code = (r.get("status") or {}).get("code")
            if code in (0, 1001, 2004, 3003):   # erkannt / kein Treffer / Stille / Limit -> Zugang ok
                return True, "Zugang funktioniert"
            return False, f"ACRCloud: {(r.get('status') or {}).get('msg', 'abgelehnt')}"
    except (httpx.HTTPError, ValueError, KeyError) as e:
        return None, f"Prüfung nicht möglich: {e}"
    return None, "unbekannter Dienst"


def save(service_id: str, values: dict[str, str]) -> None:
    for k, v in values.items():
        if k in {f.key for f in SERVICES[service_id].fields} and v:
            config.set_value(k, v.strip())


def status() -> list[dict]:
    out = []
    for s in SERVICES.values():
        have = {f.key: bool(config.opt(f.key)) for f in s.fields}
        out.append({"id": s.id, "name": s.name, "hint": s.pages_hint, "url": s.start_url,
                    "connected": all(have.values()), "partial": any(have.values()) and not all(have.values()),
                    "fields": [f.key for f in s.fields]})
    return out


# ------------------------------------------------------------------ Zwischenablage
def read_clipboard() -> str | None:
    import sys
    if sys.platform == "win32":
        cmds = [["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]]
    elif sys.platform == "darwin":
        cmds = [["pbpaste"]]
    else:
        cmds = []
    cmds += [["wl-paste", "--no-newline"], ["xclip", "-o", "-selection", "clipboard"], ["xsel", "-ob"],
            ["qdbus6", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.getClipboardContents"],
            ["qdbus", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.getClipboardContents"]]
    for c in cmds:
        if shutil.which(c[0]):
            try:
                r = subprocess.run(c, capture_output=True, text=True, timeout=2)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip()
            except (subprocess.SubprocessError, OSError):
                continue
    return None


def detect_in_clipboard(service_id: str) -> dict[str, str]:
    """Nur auf Anfrage und nur für den Dienst, den du gerade verbindest; nichts wird gespeichert."""
    text = read_clipboard()
    if not text or len(text) > 5000:
        return {}
    svc = SERVICES[service_id]
    found = {}
    # noch fehlende Felder zuerst (z.B. bei ACRCloud: Key schon da, Secret fehlt)
    for f in sorted(svc.fields, key=lambda f: bool(config.opt(f.key))):
        if config.opt(f.key) == text.strip():
            continue
        m = re.fullmatch(f.value_re.replace(r"\b", ""), text.strip())
        if m:
            found[f.key] = m.group(0)
            break   # ein Wert pro Kopiervorgang
    return found
