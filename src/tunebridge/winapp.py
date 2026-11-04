"""Windows-Desktop-App: WebView2 prüfen/nachinstallieren, Meldungen als Windows-Dialog, Eintrag in „Apps“.

Unter Windows gibt es keinen Browser-Ersatz: Das App-Fenster braucht Microsoft Edge WebView2. Fehlt es,
bietet die App an, es direkt von Microsoft zu installieren (signiert, wird vorher geprüft).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Offizieller „Evergreen Bootstrapper“ von Microsoft (klein, lädt die passende WebView2-Laufzeit)
WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
_WV2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
APP_ID = "{6B1E3C1A-5D2F-4C8E-9A7B-3F1D2E4C5A6B}"      # muss zu packaging/windows/sh-tunebridge.iss passen

MB_OK, MB_YESNO, MB_ICONERROR, MB_ICONWARNING, MB_ICONINFO, IDYES = 0x0, 0x4, 0x10, 0x30, 0x40, 6


def message(text: str, title: str = "SH-Tunebridge", flags: int = MB_OK | MB_ICONINFO) -> int:
    """Windows-Dialog (blockiert, bis er geschlossen wird). Gibt die gedrückte Taste zurück."""
    import ctypes
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x10000)   # MB_SETFOREGROUND


def webview2_version() -> str | None:
    """Installierte WebView2-Laufzeit (rechnerweit oder nur für diesen Benutzer) – None, wenn keine da ist."""
    import winreg
    keys = [(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WV2_GUID}"),
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WV2_GUID}"),
            (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{_WV2_GUID}")]
    for hive, path in keys:
        try:
            with winreg.OpenKey(hive, path) as k:
                v = str(winreg.QueryValueEx(k, "pv")[0] or "")
                if v and v != "0.0.0.0":
                    return v
        except OSError:
            continue
    return None


def _signed_by_microsoft(path: Path) -> bool:
    ps = ("$s = Get-AuthenticodeSignature -LiteralPath $env:TB_FILE; "
          "if ($s.Status -eq 'Valid' -and $s.SignerCertificate.Subject -match 'O=Microsoft Corporation') { 'OK' }")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       text=True, timeout=60, env={**os.environ, "TB_FILE": str(path)},
                       creationflags=0x08000000)                                   # CREATE_NO_WINDOW
    return r.stdout.strip() == "OK"


def install_webview2() -> bool:
    """WebView2 von Microsoft laden, Signatur prüfen und installieren. True, wenn es danach da ist."""
    import httpx
    tmp = Path(tempfile.mkdtemp(prefix="sh-tunebridge-wv2-"))
    exe = tmp / "MicrosoftEdgeWebview2Setup.exe"
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as c:
            r = c.get(WEBVIEW2_URL)
            r.raise_for_status()
            exe.write_bytes(r.content)
        if not _signed_by_microsoft(exe):
            raise RuntimeError("Die geladene Datei ist nicht von Microsoft signiert – abgebrochen.")
        subprocess.run([str(exe), "/silent", "/install"], timeout=900)
    finally:
        try:
            exe.unlink(missing_ok=True)
            tmp.rmdir()
        except OSError:
            pass
    return webview2_version() is not None


def ensure_webview2() -> bool:
    """Vor dem Fensterstart: WebView2 da? Sonst fragen und nachinstallieren."""
    if webview2_version():
        return True
    ans = message("Für das App-Fenster braucht SH-Tunebridge „Microsoft Edge WebView2“ – das fehlt auf diesem PC.\n\n"
                  "Jetzt kostenlos von Microsoft installieren? (dauert etwa eine Minute)",
                  flags=MB_YESNO | MB_ICONWARNING)
    if ans != IDYES:
        return False
    try:
        if install_webview2():
            return True
        message("WebView2 ließ sich nicht installieren. Bitte von Microsoft laden: "
                "https://developer.microsoft.com/microsoft-edge/webview2/", flags=MB_OK | MB_ICONERROR)
    except Exception as e:  # noqa: BLE001
        message(f"WebView2 ließ sich nicht installieren:\n{e}\n\nBitte von Microsoft laden: "
                "https://developer.microsoft.com/microsoft-edge/webview2/", flags=MB_OK | MB_ICONERROR)
    return False


def register_version(version: str) -> None:
    """Nach einem Selbst-Update die Versionsnummer in „Apps & Features“ nachziehen (nur wenn per Setup installiert)."""
    if not getattr(sys, "frozen", False):
        return
    import winreg
    path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            if winreg.QueryValueEx(k, "DisplayVersion")[0] != version:
                winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, version)
    except OSError:
        pass
