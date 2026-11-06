"""KI-Anbieter für Genre-Zuordnung und Song-/Playlist-Analyse.

Anbieter:
* lokal   – eingebautes llama.cpp-Modell (llm.py), nichts verlässt den Rechner
* eigen   – dein eigener OpenAI-kompatibler Server (z. B. llama-server), Adresse in den Einstellungen
* claude  – Anthropic Claude API (eigener API-Key)
* openai  – OpenAI API (eigener API-Key; gleiche Modelle wie ChatGPT/Codex)
* gemini  – Google Gemini API (eigener API-Key)
* cli_*   – auf dem Rechner installierte offizielle Programme (Claude Code, Codex CLI, Gemini CLI)

Mehrere KIs: „reihe“ = erste verfügbare antwortet, die anderen springen bei Fehlern ein;
„abstimmung“ = alle werden gefragt, übernommen wird nur, worauf sich die Mehrheit einigt.

Rechtliches / Datenschutz:
* Nur offizielle Wege: API mit eigenem Schlüssel oder das offizielle, vom Nutzer installierte Programm
  des Anbieters (es meldet sich selbst an). Login-Daten/Tokens werden NIE gelesen oder weitergegeben.
* Gesendet werden nur Künstler, Titel, Tags und ggf. Genre-Ergebnisse – kein Ton, keine Konten.
* Cloud-Anbieter sind erst nutzbar, nachdem der Nutzer einmal ausdrücklich zugestimmt hat (pro Anbieter).
* Automatische Nutzung (Genre-Notlösung nach jeder Erkennung) ist bei Cloud-Anbietern standardmäßig aus,
  weil sie Geld kosten kann.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from . import config, store
from . import debuglog as dbg

_KEY = "ai_settings"
PROVIDERS = {
    "lokal": {"name": "Lokales Modell (eingebaut)", "cloud": False, "key": None,
              "info": "Läuft komplett auf deinem Rechner (Einstellungen › Lokales LLM)."},
    "eigen": {"name": "Eigener Server (llama.cpp / OpenAI-kompatibel)", "cloud": False, "key": "LLM_KEY",
              "info": "Z. B. dein eigener llama-server im Heimnetz. Adresse wie http://127.0.0.1:8080/v1"},
    "claude": {"name": "Claude (Anthropic)", "cloud": True, "key": "TB_ANTHROPIC_KEY",
               "default_model": "claude-opus-5-5", "keys_url": "https://platform.claude.com/settings/keys",
               "terms": "https://www.anthropic.com/legal/commercial-terms",
               "privacy": "https://www.anthropic.com/legal/privacy"},
    "openai": {"name": "OpenAI (ChatGPT / Codex-Modelle)", "cloud": True, "key": "TB_OPENAI_KEY",
               "default_model": "", "keys_url": "https://platform.openai.com/api-keys",
               "terms": "https://openai.com/policies/services-agreement/",
               "privacy": "https://openai.com/policies/privacy-policy/"},
    "gemini": {"name": "Gemini (Google)", "cloud": True, "key": "TB_GEMINI_KEY",
               "default_model": "", "keys_url": "https://aistudio.google.com/apikey",
               "terms": "https://ai.google.dev/gemini-api/terms",
               "privacy": "https://policies.google.com/privacy"},
    # offizielle Programme, falls installiert – nutzen deren eigene Anmeldung (Abo oder Key), kein Key hier nötig
    "cli_claude": {"name": "Claude Code (auf diesem Rechner)", "cloud": True, "key": None, "cli": "claude",
                   "default_model": "", "info": "Nutzt dein installiertes Claude Code mit dessen Anmeldung.",
                   "terms": "https://www.anthropic.com/legal/consumer-terms",
                   "privacy": "https://www.anthropic.com/legal/privacy"},
    "cli_codex": {"name": "Codex CLI (auf diesem Rechner)", "cloud": True, "key": None, "cli": "codex",
                  "default_model": "", "info": "Nutzt deine installierte Codex CLI mit deren Anmeldung.",
                  "terms": "https://openai.com/policies/row-terms-of-use/",
                  "privacy": "https://openai.com/policies/privacy-policy/"},
    "cli_gemini": {"name": "Gemini CLI (auf diesem Rechner)", "cloud": True, "key": None, "cli": "gemini",
                   "default_model": "", "info": "Nutzt deine installierte Gemini CLI mit deren Anmeldung.",
                   "terms": "https://ai.google.dev/gemini-api/terms",
                   "privacy": "https://policies.google.com/privacy"},
}
# lokale OpenAI-kompatible Server, die wir automatisch suchen (nur 127.0.0.1, kurzer Timeout)
LOCAL_SERVERS = {"llama.cpp / llama-server": "http://127.0.0.1:8080/v1", "Ollama": "http://127.0.0.1:11434/v1",
                 "LM Studio": "http://127.0.0.1:1234/v1", "Jan": "http://127.0.0.1:1337/v1"}
DEFAULTS = {"provider": "lokal", "models": {}, "consent": {}, "auto_genre": None, "eigen_url": "", "review": False,
            "model_list": {}, "use": None, "combine": "reihe"}   # model_list: {anbieter: {"ids": [...], "t": Zeit}} – einmal abgerufen, gemerkt
# bevorzugte Modelle, falls noch keins gewählt ist (schnell + günstig reicht für Genre-Fragen)
_PREFER = {"gemini": [r"^gemini-[\d.]+-flash$", r"flash(?!.*(lite|image|tts|live|exp|preview))", r"flash", r"pro"],
           "openai": [r"^gpt-[\d.]+-mini$", r"mini", r"^gpt"],
           "claude": [r"sonnet", r"haiku", r"opus"]}


class AIError(RuntimeError):
    pass


# ------------------------------------------------------------------ Einstellungen
def settings() -> dict:
    try:
        raw = store.meta_get(_KEY)
        cur = json.loads(raw) if raw else {}
    except Exception:
        cur = {}
    s = {**DEFAULTS, **cur}
    if not isinstance(s["use"], list):          # alte Einstellung: ein einzelner Anbieter
        s["use"] = [s["provider"]] if s["provider"] in PROVIDERS else []
    s["use"] = [p for p in dict.fromkeys(s["use"]) if p in PROVIDERS]
    s["provider"] = s["use"][0] if s["use"] else "aus"    # Haupt-KI = erste in der Reihenfolge
    if s["combine"] not in ("reihe", "abstimmung"):
        s["combine"] = "reihe"
    if not s["eigen_url"] and config.opt("LLM_URL"):
        s["eigen_url"] = config.opt("LLM_URL")
    if s["auto_genre"] is None:          # lokal/eigen: an · Cloud: aus (kostet ggf. Geld)
        s["auto_genre"] = not PROVIDERS.get(s["provider"], {}).get("cloud", False)
    return s


def save_settings(patch: dict) -> dict:
    s = settings()
    if "provider" in patch:
        if patch["provider"] not in (*PROVIDERS, "aus"):
            raise AIError("Unbekannter Anbieter")
        s["use"] = [] if patch["provider"] == "aus" else [patch["provider"]]
        s["provider"] = patch["provider"]
        if "auto_genre" not in patch:
            s["auto_genre"] = None
    if "use" in patch:                     # Liste in Reihenfolge = Priorität
        use = [p for p in dict.fromkeys(patch["use"] or []) if p in PROVIDERS]
        if (use[:1] or ["aus"]) != (s["use"][:1] or ["aus"]) and "auto_genre" not in patch:
            s["auto_genre"] = None
        s["use"], s["provider"] = use, (use[0] if use else "aus")
    if "combine" in patch and patch["combine"] in ("reihe", "abstimmung"):
        s["combine"] = patch["combine"]
    if "model" in patch and s["provider"] in PROVIDERS:
        s["models"][s["provider"]] = str(patch["model"])[:100]
    for p, m in (patch.get("models") or {}).items():   # {anbieter: modell} – unabhängig vom aktiven
        if p in PROVIDERS:
            s["models"][p] = str(m)[:100]
    if "auto_genre" in patch:
        s["auto_genre"] = bool(patch["auto_genre"])
    if "review" in patch:
        s["review"] = bool(patch["review"])
    if "eigen_url" in patch:
        url = str(patch["eigen_url"]).strip().rstrip("/")
        if url and not re.match(r"^https?://", url):
            raise AIError("Adresse muss mit http:// oder https:// beginnen")
        s["eigen_url"] = url
    if "consent" in patch:               # {anbieter: true/false}
        for p, ok in patch["consent"].items():
            if p in PROVIDERS and PROVIDERS[p]["cloud"]:
                s["consent"][p] = time.time() if ok else None
    if "key" in patch and s["provider"] in PROVIDERS and PROVIDERS[s["provider"]]["key"]:
        patch.setdefault("keys", {})[s["provider"]] = patch["key"]
    for p, v in (patch.get("keys") or {}).items():    # {anbieter: key} – leer = Key löschen
        if p in PROVIDERS and PROVIDERS[p]["key"]:
            config.set_value(PROVIDERS[p]["key"], str(v or "").strip())
            s["model_list"].pop(p, None)               # neuer Key -> Modelle neu abrufen
    store.meta_set(_KEY, json.dumps({k: v for k, v in s.items()}))
    return public()


def public() -> dict:
    s = settings()
    return {**s, "providers": [{"id": k, **{x: v for x, v in p.items() if x != "key"},
                                "has_key": bool(p["key"] and config.opt(p["key"])) or bool(p.get("cli") and _which(p["cli"])),
                                "installed": bool(_which(p["cli"])) if p.get("cli") else None,
                                "ready": list(ready(k)),
                                "consented": bool(s["consent"].get(k)) if p["cloud"] else True,
                                "model": s["models"].get(k) or p.get("default_model", ""),
                                "model_list": clean_models(k, (s["model_list"].get(k) or {}).get("ids"))}
                               for k, p in PROVIDERS.items()]}


def _model(provider: str) -> str:
    s = settings()
    m = s["models"].get(provider) or PROVIDERS[provider].get("default_model")
    if not m and provider != "lokal":
        raise AIError("Bitte zuerst ein Modell auswählen")
    return m


def _which(cmd: str) -> str | None:
    found = shutil.which(cmd)
    if not found:                          # GUI-Start hat oft ein knappes PATH -> übliche Orte selbst prüfen
        for d in (Path.home() / ".local/bin", Path.home() / ".npm-global/bin", Path("/usr/local/bin"),
                  Path.home() / ".bun/bin", Path.home() / "AppData/Roaming/npm"):
            for ext in ("", ".cmd", ".exe"):
                if (d / f"{cmd}{ext}").exists():
                    return str(d / f"{cmd}{ext}")
    return found


def ready(provider: str | None = None) -> tuple[bool, str]:
    s = settings()
    if provider is None:                   # irgendeine der gewählten KIs nutzbar?
        if not s["use"]:
            return False, "KI ist ausgeschaltet"
        reasons = []
        for p in s["use"]:
            ok, why = ready(p)
            if ok:
                return True, ""
            reasons.append(why)
        return False, reasons[0]
    p = provider
    if p == "aus":
        return False, "KI ist ausgeschaltet"
    if p == "lokal":
        from . import llm
        return (True, "") if llm.settings()["enabled"] else (False, "Lokales LLM ist nicht aktiviert")
    if p == "eigen":
        return (True, "") if s["eigen_url"] else (False, "Adresse des eigenen Servers fehlt")
    info = PROVIDERS[p]
    if info.get("cli"):
        if not _which(info["cli"]):
            return False, f"{info['name']}: Programm nicht gefunden"
    elif not config.opt(info["key"]):
        return False, f"API-Key für {info['name']} fehlt"
    if not s["consent"].get(p):
        return False, f"Bitte zuerst der Datenweitergabe an {info['name']} zustimmen"
    return True, ""


# ------------------------------------------------------------------ Anfragen
def _openai_compatible(base: str, key: str | None, model: str, prompt: str, max_tokens: int,
                       local: bool = False) -> str:
    body = {"model": model or "local", "messages": [{"role": "user", "content": prompt}]}
    if local:
        body.update(max_tokens=max_tokens, temperature=0, chat_template_kwargs={"enable_thinking": False})
    else:
        body["max_completion_tokens"] = max(max_tokens, 2000)    # Reasoning-Modelle brauchen Luft
    r = httpx.post(base.rstrip("/") + "/chat/completions", json=body, timeout=120,
                   headers={"Authorization": f"Bearer {key}"} if key else {})
    if r.status_code >= 400:
        raise AIError(_err(r))
    return r.json()["choices"][0]["message"]["content"] or ""


def _err(r: httpx.Response) -> str:
    try:
        d = r.json()
        e = d.get("error") if isinstance(d, dict) else None
        msg = (e.get("message") if isinstance(e, dict) else e) or d
    except ValueError:
        msg = r.text[:200]
    return f"HTTP {r.status_code}: {str(msg)[:300]}"


def _claude(prompt: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.opt("TB_ANTHROPIC_KEY"), timeout=120.0, max_retries=2)
    model = _model("claude")
    kwargs = {}
    if model in ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"):
        # Lehnt das Modell aus Sicherheitsgründen ab, übernimmt serverseitig ein passendes anderes.
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        resp = client.beta.messages.create(
            model=model, max_tokens=max(max_tokens, 4000),
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}], **kwargs)
    except anthropic.AuthenticationError as e:
        raise AIError("Claude: API-Key ungültig") from e
    except anthropic.RateLimitError as e:
        raise AIError("Claude: Limit erreicht – bitte später erneut") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude: HTTP {e.status_code} – {e.message[:200]}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Claude nicht erreichbar") from e
    if resp.stop_reason == "refusal":
        raise AIError("Claude hat die Anfrage abgelehnt")
    return "".join(b.text for b in resp.content if b.type == "text")


def _gemini(prompt: str, max_tokens: int) -> str:
    model = _model("gemini").removeprefix("models/")
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                   headers={"x-goog-api-key": config.opt("TB_GEMINI_KEY") or ""}, timeout=120,
                   json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                         "generationConfig": {"maxOutputTokens": max(max_tokens, 2000)}})
    if r.status_code >= 400:
        raise AIError("Gemini: " + _err(r))
    parts = (((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
    return "".join(p.get("text", "") for p in parts)


def _cli(p: str, prompt: str, wait: float) -> str:
    """Offizielles Programm des Anbieters ohne Werkzeuge in einem leeren Ordner starten, Frage über stdin."""
    exe = _which(PROVIDERS[p]["cli"])
    model = settings()["models"].get(p)
    with tempfile.TemporaryDirectory(prefix="tb-ki-") as tmp:
        out_file = Path(tmp) / "antwort.txt"
        if p == "cli_claude":
            cmd = [exe, "-p", "--output-format", "text", "--tools", "", "--no-session-persistence",
                   "--strict-mcp-config"] + (["--model", model] if model else [])
        elif p == "cli_codex":
            cmd = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
                   "--output-last-message", str(out_file)] + (["-m", model] if model else []) + ["-"]
        else:
            cmd = [exe] + (["-m", model] if model else []) + ["-p", "Beantworte die Frage aus stdin."]
        # eigene Umgebung: keine Variablen einer evtl. umgebenden Claude-Code-Sitzung weiterreichen
        env = {k: v for k, v in os.environ.items() if not (k.startswith("CLAUDE") or k == "CLAUDECODE")}
        try:
            from .osutil import NO_WINDOW
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tmp, env=env,
                               timeout=max(wait, 60), encoding="utf-8", errors="replace", **NO_WINDOW)
        except subprocess.TimeoutExpired as e:
            raise AIError(f"{PROVIDERS[p]['name']}: keine Antwort in {int(max(wait, 60))} s") from e
        text = out_file.read_text(encoding="utf-8") if out_file.exists() else r.stdout
        if r.returncode != 0 and not text.strip():
            err = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["Fehler"]
            raise AIError(f"{PROVIDERS[p]['name']}: {err[0][:200]}")
        return text


def ask(prompt: str, max_tokens: int = 300, provider: str | None = None, wait: float = 90) -> str:
    """Eine Frage stellen. Ohne provider: die gewählten KIs der Reihe nach – fällt eine aus, springt die
    nächste ein. Wirft AIError, wenn keine nutzbar ist."""
    if provider is None:
        last: Exception | None = None
        for p in settings()["use"]:
            if not ready(p)[0]:
                continue
            try:
                return ask(prompt, max_tokens, p, wait)
            except Exception as e:  # noqa: BLE001 – nächste KI versuchen
                dbg.error("ki", f"{PROVIDERS[p]['name']} fehlgeschlagen – nächste KI", e)
                last = e
        raise AIError(str(last) if last else ready()[1])
    p = provider
    ok, why = ready(p)
    if not ok:
        raise AIError(why)
    t0 = time.time()
    if p == "lokal":
        from . import llm
        text = llm.chat(prompt, wait=wait, max_tokens=max_tokens) or ""
    elif p == "eigen":
        text = _openai_compatible(s["eigen_url"], config.opt("LLM_KEY"), s["models"].get("eigen") or
                                  config.opt("LLM_MODEL") or "local", prompt, max_tokens, local=True)
    elif p == "claude":
        text = _claude(prompt, max_tokens)
    elif p == "openai":
        text = _openai_compatible("https://api.openai.com/v1", config.opt("TB_OPENAI_KEY"), _model("openai"),
                                  prompt, max_tokens)
    elif p == "gemini":
        text = _gemini(prompt, max_tokens)
    elif p.startswith("cli_"):
        text = _cli(p, prompt, wait)
    else:
        raise AIError("Unbekannter Anbieter")
    dbg.event("ki", "Antwort", anbieter=p, dauer_s=round(time.time() - t0, 1), laenge=len(text))
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def ask_auto(prompt: str, max_tokens: int = 200) -> str | None:
    """Für die automatische Genre-Notlösung: nur wenn erlaubt, Fehler -> None."""
    s = settings()
    if not s["auto_genre"] or not ready()[0]:
        return None
    try:
        return ask(prompt, max_tokens)
    except Exception as e:
        dbg.error("ki", "Automatische Anfrage fehlgeschlagen", e)
        return None


def models(provider: str) -> list[str]:
    """Verfügbare Modelle beim Anbieter abfragen (statt Namen zu raten)."""
    s = settings()
    if provider == "claude":
        import anthropic
        c = anthropic.Anthropic(api_key=config.opt("TB_ANTHROPIC_KEY"), timeout=20.0)
        return [m.id for m in c.models.list()]
    if provider == "openai":
        r = httpx.get("https://api.openai.com/v1/models", timeout=20,
                      headers={"Authorization": f"Bearer {config.opt('TB_OPENAI_KEY')}"})
        if r.status_code >= 400:
            raise AIError(_err(r))
        ids = [m["id"] for m in r.json().get("data", [])]
        return sorted(i for i in ids if re.match(r"^(gpt|o\d|codex)", i) and not re.search(
            r"audio|realtime|image|transcribe|tts|embedding|search", i))
    if provider == "gemini":
        r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", timeout=20,
                      headers={"x-goog-api-key": config.opt("TB_GEMINI_KEY") or ""}, params={"pageSize": 200})
        if r.status_code >= 400:
            raise AIError(_err(r))
        return [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini" in m["name"]]
    if provider == "cli_claude":
        return ["sonnet", "opus", "haiku"]          # Kurznamen, die Claude Code selbst auflöst
    if provider in ("cli_codex", "cli_gemini"):
        return []                                    # Programm nimmt sein Standardmodell
    if provider == "eigen":
        r = httpx.get(s["eigen_url"].rstrip("/") + "/models", timeout=10,
                      headers={"Authorization": f"Bearer {config.opt('LLM_KEY')}"} if config.opt("LLM_KEY") else {})
        if r.status_code >= 400:
            raise AIError(_err(r))
        return [m["id"] for m in r.json().get("data", [])]
    return []


_NOT_TEXT = re.compile(r"tts|image|transcribe|robotics|computer-use|customtools|nano-banana|embedding|"
                       r"native-audio|live|aqa|learnlm|veo|imagen|-latest$|-\d{3}$|-\d{2}-\d{4}$")


def clean_models(provider: str, ids: list[str] | None) -> list[str] | None:
    """Nur Text-Modelle, ohne Aliase/Doppelte; stabile vor Vorschau, neueste zuerst."""
    if ids is None:
        return None
    if provider in ("gemini", "openai"):
        ids = [i for i in ids if not _NOT_TEXT.search(i)]
    ids = list(dict.fromkeys(ids))

    def key(i: str):
        ver = [int(x) for x in re.findall(r"\d+", i.split("-")[1] if "-" in i else "")] or [0]
        return (bool(re.search(r"preview|exp|beta", i)), [-v for v in ver], len(i), i)
    return sorted(ids, key=key) if provider in ("gemini", "openai") else ids


def detect() -> dict:
    """Was ist auf diesem Rechner an KI vorhanden? (Programme + lokale Server, nur 127.0.0.1)"""
    progs = {k: bool(_which(p["cli"])) for k, p in PROVIDERS.items() if p.get("cli")}
    servers = []
    for name, url in LOCAL_SERVERS.items():
        try:
            r = httpx.get(url + "/models", timeout=0.6)
            if r.status_code < 500:
                ids = [m.get("id") for m in (r.json().get("data") or [])] if r.status_code == 200 else []
                servers.append({"name": name, "url": url, "models": ids[:20]})
        except (httpx.HTTPError, ValueError):
            pass
    return {"programme": progs, "server": servers}


def pick_default(provider: str, ids: list[str]) -> str:
    for pat in _PREFER.get(provider, []):
        hit = sorted((i for i in ids if re.search(pat, i)), reverse=True)
        if hit:
            return hit[0]
    return ids[0] if ids else ""


def refresh_models(provider: str, force: bool = False) -> list[str]:
    """Modelle einmal beim Anbieter abrufen und merken; ist noch keins gewählt, ein passendes vorwählen."""
    s = settings()
    hit = s["model_list"].get(provider)
    if hit and not force:
        return clean_models(provider, hit["ids"])
    ids = clean_models(provider, models(provider)) or []
    s["model_list"][provider] = {"ids": ids, "t": time.time()}
    cur = s["models"].get(provider) or PROVIDERS[provider].get("default_model")
    if ids and cur not in ids and not provider.startswith("cli_"):
        s["models"][provider] = pick_default(provider, ids)
    store.meta_set(_KEY, json.dumps(s))
    return ids


# ------------------------------------------------------------------ Analysen
def voters() -> list[str]:
    """KIs, die bei „abstimmung“ gefragt werden (nur nutzbare, in Reihenfolge). Sonst nur eine."""
    s = settings()
    ok = [p for p in s["use"] if ready(p)[0]]
    return ok if s["combine"] == "abstimmung" and len(ok) >= 2 else ok[:1]


def ask_all(prompt: str, max_tokens: int, wait: float) -> dict[str, str]:
    """Alle abstimmenden KIs gleichzeitig fragen -> {anbieter: antwort}. Fehler einzelner werden geloggt."""
    ps = voters()
    if len(ps) <= 1:
        return {(ps or ["?"])[0]: ask(prompt, max_tokens, wait=wait)}
    out: dict[str, str] = {}
    with ThreadPoolExecutor(len(ps)) as ex:
        futs = {p: ex.submit(ask, prompt, max_tokens, p, wait) for p in ps}
        for p, f in futs.items():
            try:
                out[p] = f.result()
            except Exception as e:  # noqa: BLE001
                dbg.error("ki", f"Abstimmung: {PROVIDERS[p]['name']} fehlgeschlagen", e)
    if not out:
        raise AIError("Keine der gewählten KIs hat geantwortet")
    return out


def _majority(values: list) -> tuple[object, int]:
    from collections import Counter
    c = Counter(v for v in values if v)
    return c.most_common(1)[0] if c else (None, 0)


def _json(text: str) -> dict:
    try:
        return json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError as e:
        raise AIError("Die KI hat keine auswertbare Antwort geliefert") from e


def analyze_track(t: dict) -> dict:
    """t: {artist, title, album?, tags?, genre?, subgenre?, bpm?, year?}"""
    from .genres import TAXONOMY
    prompt = (
        "You are an expert music curator. Analyse this song using only what you actually know.\n"
        f"Song: {t.get('artist')} - {t.get('title')}\n"
        f"Album: {t.get('album') or '-'} · Year: {t.get('year') or '-'} · BPM: {t.get('bpm') or '-'}\n"
        f"Community tags: {', '.join(list(t.get('tags') or [])[:20]) or '-'}\n"
        f"Current classification: {t.get('genre') or '-'} / {t.get('subgenre') or '-'}\n"
        f"Main genre options: {', '.join(TAXONOMY)}\n\n"
        "Answer in German. If you do not know the song or artist, set known=false and do not invent facts.\n"
        'Reply only with JSON: {"known": true|false, "genre": "<one main genre option or null>", '
        '"subgenre": "<subgenre or null>", "nische": "<most specific style or null>", '
        '"stimmung": ["..."], "energie": "niedrig|mittel|hoch", "tempo": "<z. B. 170-175 BPM or null>", '
        '"aehnliche_kuenstler": ["..."], "beschreibung": "<2-3 Sätze>", "sicherheit": 0.0-1.0, '
        '"ki_generiert": "ja|nein|unbekannt", "ki_begruendung": "<nur wenn du konkret weißt, dass Künstler/Song '
        'KI-generiert ist (z. B. bekanntes Suno-Projekt), sonst null>"}')
    answers = {}
    for p, text in ask_all(prompt, 700, 180).items():
        try:
            answers[p] = _json(text)
        except AIError as e:
            dbg.error("ki", f"{p}: Antwort nicht auswertbar", e)
    if not answers:
        raise AIError("Die KI hat keine auswertbare Antwort geliefert")
    order = list(answers)
    if len(answers) == 1:
        d = answers[order[0]]
        d["anbieter"] = order[0]
        return d
    # Abstimmung: Hauptgenre per Mehrheit, Subgenre per Mehrheit unter denen, die beim Genre zustimmen
    g, n = _majority([a.get("genre") for a in answers.values() if a.get("known", True)])
    need = len(answers) // 2 + 1
    agree = [p for p in order if g and answers[p].get("genre") == g]
    base = answers[agree[0]] if agree and n >= need else answers[order[0]]
    d = dict(base)
    if agree and n >= need:
        sg, m = _majority([answers[p].get("subgenre") for p in agree])
        d["subgenre"] = sg if m >= 2 or len(agree) == 1 else base.get("subgenre")
        d["sicherheit"] = round(min(1.0, max(float(a.get("sicherheit") or 0) for a in answers.values()) * n / len(answers)), 2)
    else:
        d["uneinig"] = True
        d["sicherheit"] = round(min(float(d.get("sicherheit") or 0.5), 0.4), 2)
    d["anbieter"] = "+".join(order)
    d["abstimmung"] = {p: f"{a.get('genre') or '?'} / {a.get('subgenre') or '-'}" for p, a in answers.items()}
    return d


def analyze_playlist(name: str, tracks: list[dict]) -> dict:
    """Songliste (max. 150) -> Einschätzung. Verteilung der Genres rechnet die App selbst."""
    from collections import Counter
    tracks = tracks[:150]
    dist = Counter(t.get("genre") or "unbekannt" for t in tracks)
    lines = "\n".join(f"- {t.get('artist')} - {t.get('title')} [{t.get('genre') or '?'} / {t.get('subgenre') or '?'}]"
                      for t in tracks)
    prompt = (
        "You are an expert music curator. Analyse this playlist.\n"
        f"Name: {name or '-'}\nSongs ({len(tracks)}):\n{lines}\n\n"
        "Answer in German. Do not invent facts about songs you do not know.\n"
        'Reply only with JSON: {"stil": "<1-2 Sätze Gesamteindruck>", "stimmung": ["..."], '
        '"passt_nicht": ["<Künstler - Titel, die stilistisch herausfallen>"], '
        '"aufteilen": [{"name": "<Vorschlag Playlist-Name>", "beschreibung": "..."}], '
        '"empfehlungen": ["<Künstler, die passen würden>"]}')
    d = _json(ask(prompt, 1200, wait=240))
    d["verteilung"] = dict(dist.most_common())
    d["anbieter"] = settings()["provider"]
    return d


def review_genres(items: list[dict], chunk: int = 60) -> list[dict]:
    """KI prüft die Genre-Zuordnung einer Songliste. -> [{i, genre, subgenre, grund}] nur für sichere Korrekturen.
    Die KI darf nur Genres/Subgenres aus unserer Liste wählen; alles andere wird verworfen.
    Gesendet werden nur Künstler, Titel, Tags und das bisherige Ergebnis – in Blöcken (Kosten/Antwortlänge)."""
    from .genres import TAXONOMY
    subs = {g: [s for s in v if s != "_"] for g, v in TAXONOMY.items()}
    allowed = "\n".join(f"- {g}: {', '.join(v) or '-'}" for g, v in subs.items())
    out: list[dict] = []
    for start in range(0, len(items), chunk):
        block = items[start:start + chunk]
        lines = "\n".join(
            f"{start + n}. {it.get('artist')} - {it.get('title')} | jetzt: {it.get('genre') or '?'} / "
            f"{it.get('subgenre') or '-'} | tags: {', '.join(list(it.get('tags') or [])[:8]) or '-'}"
            for n, it in enumerate(block))
        prompt = (
            "You are an expert music curator checking automatic genre labels.\n"
            f"Allowed main genres and their subgenres:\n{allowed}\n\n"
            f"Songs (number. artist - title | current label | community tags):\n{lines}\n\n"
            "Only correct a label if you actually know the song or artist and the current label is clearly wrong "
            "or a clearly better subgenre exists. Do not guess for songs you do not know. "
            "Use exactly the names from the allowed list.\n"
            'Reply only with JSON: {"fixes": [{"i": <number>, "genre": "<main genre>", "subgenre": "<subgenre or null>", '
            '"grund": "<kurz, deutsch>"}]}')
        try:
            replies = ask_all(prompt, 1500, 240)
        except AIError as e:
            if not out and start == 0:
                raise
            dbg.error("ki", "KI-Prüfung: Block übersprungen", e)
            continue
        votes: dict[int, list[tuple[str, str | None, str]]] = {}
        for text in replies.values():
            try:
                fixes = _json(text).get("fixes") or []
            except AIError:
                continue
            for f in fixes:
                try:
                    i, g, sg = int(f["i"]), f.get("genre"), f.get("subgenre") or None
                except (KeyError, TypeError, ValueError):
                    continue
                if not (start <= i < start + len(block)) or g not in TAXONOMY or (sg and sg not in subs[g]):
                    continue
                if (g, sg) == (items[i].get("genre"), items[i].get("subgenre")):
                    continue
                votes.setdefault(i, []).append((g, sg, str(f.get("grund") or "")[:200]))
        need = len(replies) // 2 + 1          # 1 von 1 · 2 von 2 · 2 von 3 – Mehrheit der Antworten
        for i, vs in sorted(votes.items()):
            g, n = _majority([v[0] for v in vs])
            if n < need:
                continue
            sg, m = _majority([v[1] for v in vs if v[0] == g])
            if m < need:
                sg = items[i].get("subgenre") if items[i].get("genre") == g else None
            if (g, sg) == (items[i].get("genre"), items[i].get("subgenre")):
                continue
            grund = next(v[2] for v in vs if v[0] == g)
            if len(replies) > 1:
                grund = f"{grund} ({n} von {len(replies)} KIs einig)"
            out.append({"i": i, "genre": g, "subgenre": sg, "grund": grund})
    dbg.event("ki", f"KI-Prüfung: {len(out)} Korrekturen bei {len(items)} Songs", anbieter=settings()["provider"])
    return out


def judge_genres(items: list[dict], chunk: int = 40, cancel=None) -> list[dict]:
    """Eigenes KI-Urteil für die Genre-Datenbank. Die KI bekommt NUR Fakten: Künstler, Titel, Album, BPM –
    ausdrücklich keine Tags oder Genres von Spotify/TIDAL/Last.fm/Deezer und kein bisheriges Ergebnis
    (sonst wäre es nur umgeschriebene Fremd-Daten). -> [{i, genre, subgenre, n}] für Songs, die die KI kennt."""
    from .genres import TAXONOMY
    subs = {g: [s for s in v if s != "_"] for g, v in TAXONOMY.items()}
    allowed = "\n".join(f"- {g}: {', '.join(v) or '-'}" for g, v in subs.items())
    out: list[dict] = []
    for start in range(0, len(items), chunk):
        if cancel and cancel():
            break
        block = items[start:start + chunk]
        lines = "\n".join(
            f"{start + n}. {', '.join(it.get('artists') or [])} - {it.get('title')}"
            f"{' | album: ' + it['album'] if it.get('album') else ''}{' | ' + str(round(it['bpm'])) + ' bpm' if it.get('bpm') else ''}"
            for n, it in enumerate(block))
        prompt = (
            "You are an expert music curator. Classify each song by genre from your own knowledge.\n"
            f"Allowed main genres and their subgenres:\n{allowed}\n\n"
            f"Songs (number. artists - title | album | tempo):\n{lines}\n\n"
            "Only answer for songs or artists you actually know. Skip songs you do not know – do not guess. "
            "A genre named in the title (e.g. '(Hardtekk Remix)') counts. Use exactly the names from the allowed list.\n"
            'Reply only with JSON: {"songs": [{"i": <number>, "genre": "<main genre>", "subgenre": "<subgenre or null>"}]}')
        try:
            replies = ask_all(prompt, 2500, 300)
        except AIError as e:
            if not out and start == 0:
                raise
            dbg.error("ki", "KI-Urteil: Block übersprungen", e)
            continue
        votes: dict[int, list[tuple[str, str | None]]] = {}
        for text in replies.values():
            try:
                got = _json(text).get("songs") or []
            except AIError:
                continue
            for f in got:
                try:
                    i, g, sg = int(f["i"]), f.get("genre"), f.get("subgenre") or None
                except (KeyError, TypeError, ValueError):
                    continue
                if not (start <= i < start + len(block)) or g not in TAXONOMY:
                    continue
                votes.setdefault(i, []).append((g, sg if sg in subs[g] else None))
        need = len(replies) // 2 + 1
        for i, vs in sorted(votes.items()):
            g, n = _majority([v[0] for v in vs])
            if n < need:
                continue
            sg, m = _majority([v[1] for v in vs if v[0] == g])
            out.append({"i": i, "genre": g, "subgenre": sg if m >= need else None, "n": n})
    dbg.event("ki", f"KI-Urteil (nur Fakten): {len(out)} von {len(items)} Songs eingeschätzt")
    return out
