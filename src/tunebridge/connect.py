"""Login-Fenster je Dienst (nur in der Desktop-App) – liest nach dem Login die Keys ab."""

from __future__ import annotations

import json
import threading
import time
import webbrowser

from . import keys

_sessions: dict[str, dict] = {}
_lock = threading.Lock()
TIMEOUT = 15 * 60


def _mask(v: str) -> str:
    return v[:4] + "•" * 6 + v[-2:] if len(v) > 8 else "•" * len(v)


def session(svc: str) -> dict:
    with _lock:
        s = dict(_sessions.get(svc) or {"state": "idle"})
    s["found"] = {k: _mask(v) for k, v in (s.get("values") or {}).items()}
    s.pop("values", None)
    s.pop("token", None)
    return s


def _set(svc: str, **kw) -> None:
    with _lock:
        _sessions.setdefault(svc, {}).update(kw)


def _desktop_available() -> bool:
    try:
        import webview
        return bool(webview.windows)
    except ImportError:
        return False


BANNER_JS = r"""
((msg, back, state) => {
  let b = document.getElementById("__tb_banner");
  if (!b) {
    b = document.createElement("div"); b.id = "__tb_banner";
    b.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483647;display:flex;align-items:center;gap:12px;" +
      "padding:10px 16px;background:#12151a;color:#e4e6ea;font:500 13.5px/1.4 Inter,system-ui,sans-serif;" +
      "border-bottom:1px solid #6cc8a8;box-shadow:0 4px 18px rgba(0,0,0,.35)";
    b.innerHTML = '<span style="width:9px;height:9px;border-radius:50%;background:#6cc8a8;flex:none"></span>' +
      '<b style="font-weight:650">SH-Tunebridge</b><span id="__tb_msg" style="color:#a2a8b2"></span>' +
      '<a id="__tb_back" style="margin-left:auto;color:#0d1a15;background:#6cc8a8;padding:6px 12px;border-radius:7px;' +
      'text-decoration:none;font-weight:600;cursor:pointer">Zurück zu SH-Tunebridge</a>';
    (document.body || document.documentElement).appendChild(b);
    document.documentElement.style.scrollPaddingTop = "52px";
    if (document.body) document.body.style.marginTop = "48px";
  }
  b.querySelector("#__tb_msg").textContent = msg;
  b.querySelector("#__tb_back").href = back;
  b.style.borderBottomColor = state === "saved" ? "#6cc8a8" : state === "error" ? "#e2786e" : "#6cc8a8";
  return true;
})
"""


def start(svc_id: str) -> str:
    """-> 'window' (Login im App-Fenster) oder 'browser' (Systembrowser + Zwischenablage)."""
    svc = keys.SERVICES[svc_id]
    if not _desktop_available():
        webbrowser.open(svc.start_url)
        _set(svc_id, state="browser", message="Seite im Browser geöffnet – Key kopieren, SH-Tunebridge erkennt ihn.",
             values={}, started=time.time())
        return "browser"

    import webview
    win = webview.windows[0]
    app_url = (win.get_current_url() or "http://127.0.0.1:8765/").split("#")[0]
    back = app_url + "#/settings"
    with _lock:
        _sessions[svc_id] = {"state": "waiting", "message": "Logge dich ein …", "values": {}, "started": time.time(),
                             "token": time.time()}
        token = _sessions[svc_id]["token"]
    win.load_url(svc.start_url)
    threading.Thread(target=_watch, args=(svc_id, win, app_url, back, token), daemon=True).start()
    return "window"


def _still_current(svc_id: str, token: float) -> bool:
    return (_sessions.get(svc_id) or {}).get("token") == token


def _watch(svc_id: str, win, app_url: str, back: str, token: float) -> None:
    svc = keys.SERVICES[svc_id]
    values: dict[str, str] = {}
    rejected: set[str] = set()
    prefilled_url = None
    t0 = time.time()
    left_app = False

    def banner(msg: str, state: str = "") -> None:
        try:
            win.evaluate_js(BANNER_JS + "(" + json.dumps(msg) + "," + json.dumps(back) + "," + json.dumps(state) + ")")
        except Exception:
            pass

    while time.time() - t0 < TIMEOUT and _still_current(svc_id, token):
        time.sleep(1.2)
        try:
            url = win.get_current_url() or ""
        except Exception:
            continue
        if url.startswith(app_url):
            if left_app:   # Nutzer ist zurück in tunebridge, ohne dass ein Key gefunden wurde
                if (_sessions.get(svc_id) or {}).get("state") not in ("saved",):
                    _set(svc_id, state="closed", message="Abgebrochen – kein Key übernommen.")
                return
            continue
        left_app = True
        state = (_sessions.get(svc_id) or {}).get("state")
        banner(f"{svc.name} verbinden – {(_sessions.get(svc_id) or {}).get('message') or svc.pages_hint}", state)
        try:
            if svc.prefill and url != prefilled_url and "/create" in url:
                win.evaluate_js(keys.PREFILL_JS + "(" + json.dumps(svc.prefill) + ")")
                prefilled_url = url
            text = win.evaluate_js(keys.EXTRACT_JS) or ""
        except Exception:
            continue  # Seite lädt gerade
        text = text.replace("SH-Tunebridge", "")  # eigene Leiste nicht mitlesen
        for k, v in keys.extract(svc, text).items():
            if v not in rejected:
                values.setdefault(k, v)
        if not values:
            if state not in ("waiting",):
                _set(svc_id, state="waiting", message="Logge dich ein – der Key wird automatisch übernommen.")
            continue
        need = [f.key for f in svc.fields if f.key not in values and not keys.config.opt(f.key)]
        if need:
            _set(svc_id, state="partial", values=dict(values),
                 message=f"{len(values)} von {len(svc.fields)} Angaben gefunden – öffne die Seite mit dem Rest.")
            continue
        _set(svc_id, state="checking", values=dict(values), message="Key gefunden – prüfe beim Dienst …")
        banner(f"{svc.name}: Key gefunden – prüfe …", "checking")
        merged = {f.key: values.get(f.key) or keys.config.opt(f.key) or "" for f in svc.fields}
        ok, msg = keys.validate(svc_id, merged)
        if ok is False:
            rejected.update(values.values())
            values.clear()
            _set(svc_id, state="waiting", values={}, message=f"{msg} – suche weiter …")
            continue
        keys.save(svc_id, values)
        _set(svc_id, state="saved", message=msg if ok else "Gespeichert (konnte nicht geprüft werden)",
             finished=time.time())
        banner(f"{svc.name} verbunden ✓ – zurück zu SH-Tunebridge …", "saved")
        time.sleep(1.5)
        try:
            win.load_url(back)
        except Exception:
            pass
        return
    if _still_current(svc_id, token) and (_sessions.get(svc_id) or {}).get("state") != "saved":
        _set(svc_id, state="closed", message="Zeit abgelaufen – kein Key übernommen.")


def clipboard(svc_id: str) -> dict:
    found = keys.detect_in_clipboard(svc_id)
    if found:
        _set(svc_id, clip=found)
    return {k: _mask(v) for k, v in found.items()}


def accept_clipboard(svc_id: str) -> tuple[bool | None, str]:
    with _lock:
        found = (_sessions.get(svc_id) or {}).pop("clip", None)
    if not found:
        return None, "Nichts zum Übernehmen"
    svc = keys.SERVICES[svc_id]
    merged = {f.key: found.get(f.key) or keys.config.opt(f.key) or "" for f in svc.fields}
    ok, msg = keys.validate(svc_id, merged)
    if ok is False:
        return False, msg
    keys.save(svc_id, found)
    _set(svc_id, state="saved" if all(merged.values()) else "partial", message=msg)
    return ok, msg
