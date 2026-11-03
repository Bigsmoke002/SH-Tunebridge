"""Eigenes App-Fenster über pywebview.

Linux: Qt (PySide6). Windows: Edge WebView2 (ist in Windows 10/11 enthalten). macOS: WebKit (Cocoa).
Fallback: Chromium/Brave im App-Modus, sonst der Standardbrowser."""

from __future__ import annotations

from . import osutil

import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

HOST, PORT = "127.0.0.1", int(os.environ.get("TUNEBRIDGE_APP_PORT") or 8765)   # anderer Port nur für Tests


def _port_open() -> bool:
    with socket.socket() as s:
        return s.connect_ex((HOST, PORT)) == 0


def _serve() -> None:
    import uvicorn

    uvicorn.Server(uvicorn.Config("tunebridge.web.app:app", host=HOST, port=PORT, log_level="warning")).run()


def run() -> None:
    url = f"http://{HOST}:{PORT}"
    os.environ["TUNEBRIDGE_PORT"] = str(PORT)
    if os.environ.get("APPIMAGE"):
        try:  # Startmenü-Eintrag anlegen/aktualisieren (Pfad kann sich nach Updates/Verschieben ändern)
            from .update import heal_old_paths, integrate_desktop
            integrate_desktop()
            heal_old_paths()      # alte Starter nach Updates bis v0.6.0 wieder lauffähig machen
        except Exception as e:
            print("Startmenü-Eintrag nicht möglich:", e)
    if not _port_open():
        threading.Thread(target=_serve, daemon=True).start()
        for _ in range(100):
            if _port_open():
                break
            time.sleep(0.05)

    # Tray/Schwebe-Icon gleich mit starten – nicht erst, wenn das App-Fenster fertig geladen ist
    threading.Thread(target=_companion_early, daemon=True).start()

    # Qt WebEngine (pip-Build) rendert mit NVIDIA unter Wayland nur Pixelmüll ("GBM is not supported").
    # Die Oberfläche ist leicht – Software-Rendering ist flüssig genug und läuft überall.
    # Mit TUNEBRIDGE_GPU=1 lässt sich die GPU wieder einschalten.
    if osutil.LINUX:
        _qt_env()
    try:
        import webview  # pywebview – optionales Extra "desktop"
    except ImportError:
        webview = None

    if webview is not None:
        webview.settings["ALLOW_DOWNLOADS"] = True
        win = webview.create_window("SH-Tunebridge", url, width=1320, height=860, min_size=(900, 620),
                                    background_color="#0e1013", text_select=True)
        _hooks(win)
        store = osutil.data_dir() / "webview"
        if osutil.LINUX and not store.exists() and os.path.isdir(os.path.expanduser("~/.local/share/tunebridge-webview")):
            store = os.path.expanduser("~/.local/share/tunebridge-webview")  # bisheriger Ort (Linux)
        icon = _window_icon()
        if osutil.LINUX:
            try:   # Wayland: Fenster dem Startmenü-Eintrag „tunebridge.desktop“ zuordnen (Symbol in Taskleiste)
                from PySide6.QtGui import QGuiApplication
                QGuiApplication.setDesktopFileName("tunebridge")
            except Exception:  # noqa: BLE001
                pass
        try:
            webview.start(gui="qt" if osutil.LINUX else None, private_mode=False, storage_path=str(store),
                          icon=str(icon) if icon else None)
        except Exception as e:  # noqa: BLE001 – kein Fenster möglich: im Browser weitermachen statt still zu enden
            from . import debuglog
            debuglog.error("desktop", "App-Fenster konnte nicht starten – öffne im Browser", e)
        else:
            # Fenster zu = App zu: offene Hintergrundarbeiten (Login-Warten, Downloads) nicht abwarten.
            # Der LLM-Server endet mit (Linux: PDEATHSIG, sonst atexit), Datenbank-Schreibvorgänge sind Transaktionen.
            _quit()

    for b in ("chromium", "brave", "google-chrome-stable", "vivaldi"):
        if osutil.LINUX and shutil.which(b):
            subprocess.Popen([b, f"--app={url}", "--class=tunebridge", "--window-size=1320,860"])
            break
    else:
        import webbrowser
        webbrowser.open(url)
    try:
        while True:  # Server weiterlaufen lassen, solange das Fenster offen ist
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def _window_icon() -> Path | None:
    """Fenstersymbol je System: Windows (WinForms) braucht .ico – eine .svg lässt das Fenster sofort abstürzen.
    macOS nimmt das Symbol aus dem Programm-Bundle."""
    static = Path(__file__).parent / "web" / "static"
    icon = static / "icon.svg" if osutil.LINUX else static / "icon.ico" if osutil.WINDOWS else None
    return icon if icon and icon.exists() else None


def _quit() -> None:
    from . import llm
    llm.stop()
    os._exit(0)


def _hooks(win) -> None:
    """Tray/Schwebe-Icon: Fenster zeigen, App beenden; Schließen versteckt nur, solange das Tray-Symbol an ist."""
    from .web import app as web

    def show():
        # Wayland erlaubt kein „nach vorne holen“ fremder Fenster – neu einblenden (hide/show) bringt es nach vorn
        if osutil.LINUX and os.environ.get("WAYLAND_DISPLAY"):
            win.hide()
            time.sleep(0.12)
        win.show()
        win.restore()

    def closing():
        try:
            if web._comp_cfg()["tray"] and web._companion["proc"] and web._companion["proc"].poll() is None:
                threading.Timer(0.05, win.hide).start()   # nicht im Qt-Ereignis selbst (sonst Verklemmung)
                return False          # nicht schließen – läuft im Tray weiter
        except Exception:  # noqa: BLE001
            pass
        return True

    def gui(fn, timeout: float = 3.0):
        """fn im Qt-Hauptthread ausführen und das Ergebnis zurückgeben (nur Linux/Qt)."""
        from PySide6 import QtCore
        app = QtCore.QCoreApplication.instance()
        if app is None:
            raise RuntimeError("Kein Qt-Fenster")
        out, ev = {}, threading.Event()

        def run():
            try:
                out["v"] = fn()
            except Exception as e:  # noqa: BLE001
                out["e"] = e
            ev.set()
        QtCore.QTimer.singleShot(0, app, run)
        if not ev.wait(timeout):
            raise TimeoutError("Fenster antwortet nicht")
        if "e" in out:
            raise out["e"]
        return out.get("v")

    def clipboard_get() -> str:
        from PySide6.QtGui import QGuiApplication
        return gui(lambda: QGuiApplication.clipboard().text())

    def clipboard_set(text: str) -> None:
        from PySide6.QtGui import QGuiApplication
        gui(lambda: QGuiApplication.clipboard().setText(text))

    def enable_paste():
        # pywebview schaltet das Rechtsklick-Menü ab -> eigenes Menü in der Oberfläche; dafür darf die Seite
        # auf Klick hin einfügen/kopieren (nur unsere eigene Seite wird in diesem Fenster geladen)
        try:
            from PySide6.QtWebEngineCore import QWebEngineSettings

            def apply():
                st = win.native.webview.page().settings()
                for a in ("JavascriptCanPaste", "JavascriptCanAccessClipboard"):
                    if hasattr(QWebEngineSettings.WebAttribute, a):
                        st.setAttribute(getattr(QWebEngineSettings.WebAttribute, a), True)
            gui(apply)
        except Exception:  # noqa: BLE001 – andere Plattform/ältere Qt-Version: Server-Zwischenablage greift
            pass

    def loaded():
        if osutil.LINUX:
            enable_paste()
        web.companion_ensure(PORT)

    web.WINDOW_HOOKS.update(show=show, quit=_quit)
    if osutil.LINUX:
        web.WINDOW_HOOKS.update(clipboard_get=clipboard_get, clipboard_set=clipboard_set)
    win.events.closing += closing
    win.events.loaded += loaded


def _companion_early() -> None:
    try:
        from .web import app as web
        web.companion_ensure(PORT)
    except Exception as e:  # noqa: BLE001 – ohne Begleiter läuft die App trotzdem
        print("Begleiter nicht gestartet:", e)


def _qt_env() -> None:
    flags = ["--autoplay-policy=no-user-gesture-required"]
    if os.environ.get("TUNEBRIDGE_GPU") != "1":
        flags += ["--disable-gpu", "--disable-gpu-compositing"]
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(
        [os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", ""), *flags]).strip()

    # PySide6 (LGPL) statt PyQt6 (GPL) – damit SH-Tunebridge unter eigener Lizenz weitergegeben werden darf
    os.environ.setdefault("QT_API", "pyside6")
