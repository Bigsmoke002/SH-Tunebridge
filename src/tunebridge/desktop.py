"""Eigenes App-Fenster über pywebview.

Linux: Qt (PySide6). Windows: Edge WebView2 (fehlt es, wird es angeboten und von Microsoft installiert).
macOS: WebKit (Cocoa).
Windows ist immer eine Desktop-App: kein Browser-Ersatz – ein Fehler wird als Windows-Dialog gezeigt und
unter <Daten>/logs/fenster-fehler.txt gespeichert. Linux/macOS: notfalls Chromium/Brave im App-Modus bzw. Browser."""

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

    # Zeichenweg (Software / GPU über Vulkan) wählen – siehe _gpu_mode
    if osutil.LINUX:
        _qt_env()
    try:
        import webview  # pywebview – optionales Extra "desktop"
    except ImportError:
        webview = None

    if osutil.WINDOWS:
        from . import winapp
        try:
            winapp.register_version(__import__("tunebridge").__version__)
        except Exception:  # noqa: BLE001
            pass
        if webview is None:
            _window_failed(RuntimeError("Fensterteil (pywebview) fehlt im Programm"))
        if not winapp.ensure_webview2():
            _quit()

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
            webview.start(gui="qt" if osutil.LINUX else "edgechromium" if osutil.WINDOWS else None,
                          private_mode=False, storage_path=str(store), icon=str(icon) if icon else None)
        except Exception as e:  # noqa: BLE001
            if osutil.WINDOWS:
                _window_failed(e)          # Windows: Dialog statt Browser
            from . import debuglog         # Linux/macOS: im Browser weitermachen statt still zu enden
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


def _window_failed(e: BaseException) -> None:
    """Windows: Fenster ging nicht auf -> Grund immer lokal speichern, als Dialog zeigen, App beenden."""
    import traceback
    from datetime import datetime
    from .web import app as web
    web.WINDOW_STATE.update(error=f"{type(e).__name__}: {e}")
    try:
        log = osutil.data_dir() / "logs" / "fenster-fehler.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"{datetime.now():%Y-%m-%d %H:%M:%S}\n{''.join(traceback.format_exception(e))}", encoding="utf-8")
    except Exception:  # noqa: BLE001
        log = None
    try:
        from . import debuglog
        debuglog.error("desktop", "App-Fenster konnte nicht starten", e)
        from . import winapp
        winapp.message(f"Das App-Fenster konnte nicht starten:\n{type(e).__name__}: {e}\n\n"
                       + (f"Details: {log}\n\n" if log else "")
                       + "Hilft meist: SH-Tunebridge neu installieren (Setup) oder Microsoft Edge WebView2 neu installieren.\n"
                       "Fehler melden: https://github.com/Bigsmoke002/SH-Tunebridge/issues",
                       flags=winapp.MB_OK | winapp.MB_ICONERROR)
    finally:
        _quit()


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
        meter_pause(False)

    def meter_pause(on: bool) -> None:
        def run():
            try:
                win.evaluate_js(f"typeof Meter !== 'undefined' && Meter.{'suspend' if on else 'resume'}()")
            except Exception:  # noqa: BLE001 – Seite noch nicht geladen o. Ä.
                pass
        threading.Thread(target=run, daemon=True).start()   # evaluate_js wartet auf Qt – nicht im Ereignis selbst

    def closing():
        try:
            if web._comp_cfg()["tray"] and web._companion["proc"] and web._companion["proc"].poll() is None:
                meter_pause(True)
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

    def gpu_ok():
        try:
            (osutil.data_dir() / GPU_TRY).unlink(missing_ok=True)
        except OSError:
            pass

    def loaded():
        if osutil.LINUX:
            enable_paste()
            threading.Timer(5.0, gpu_ok).start()   # Fenster läuft stabil mit dem gewählten Zeichenweg
        web.companion_ensure(PORT)

    web.WINDOW_HOOKS.update(show=show, quit=_quit)
    if osutil.LINUX:
        web.WINDOW_HOOKS.update(clipboard_get=clipboard_get, clipboard_set=clipboard_set)
    win.events.closing += closing
    win.events.loaded += loaded
    win.events.shown += lambda: (web.WINDOW_STATE.update(shown=True), meter_pause(False))
    # Minimiert oder im Tray: Qt meldet der Seite das nicht zuverlässig als „versteckt“ und zeichnet weiter →
    # Pegelanzeige (WebSocket + Aufnahme) selbst anhalten, beim Wiederherstellen fortsetzen.
    # Unter Wayland kommt „minimiert“ gar nicht bei Qt an (kein solcher Zustand im Protokoll) – dort greift nur das Tray.
    win.events.minimized += lambda: meter_pause(True)
    win.events.restored += lambda: meter_pause(False)
    if hasattr(win.events, "maximized"):
        win.events.maximized += lambda: meter_pause(False)
    web.WINDOW_HOOKS.update(meter_pause=meter_pause)


def _companion_early() -> None:
    try:
        from .web import app as web
        web.companion_ensure(PORT)
    except Exception as e:  # noqa: BLE001 – ohne Begleiter läuft die App trotzdem
        print("Begleiter nicht gestartet:", e)


GPU_TRY = "gpu-versuch"   # Merker: Start mit GPU läuft; bleibt er liegen, ist das Fenster dabei abgestürzt


def _nvidia() -> bool:
    return os.path.exists("/proc/driver/nvidia/version") or os.path.isdir("/sys/module/nvidia")


def _vulkan() -> bool:
    import ctypes.util
    if not ctypes.util.find_library("vulkan"):
        return False
    dirs = ["/usr/share/vulkan/icd.d", "/etc/vulkan/icd.d", "/usr/local/share/vulkan/icd.d"]
    return any(os.path.isdir(d) and any("nvidia" in f.lower() for f in os.listdir(d)) for d in dirs)


def _gpu_tries() -> int:
    try:
        return int((osutil.data_dir() / GPU_TRY).read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return 0


def _gpu_mode() -> str:
    """Wie das Fenster zeichnet: "software", "vulkan" (GPU über Vulkan) oder "gpu" (Chromium-Standard).

    Qt WebEngine (pip-Build) zeigt mit NVIDIA unter Wayland über OpenGL nur Pixelmüll ("GBM is not supported"),
    auch über XWayland. Über Vulkan als Qt-Grafikweg klappt es und spart rund ein Drittel Rechenzeit.
    Andere Systeme bleiben vorerst beim erprobten Software-Zeichnen.
    TUNEBRIDGE_GPU=0 erzwingt Software, =1 die GPU (Chromium-Standard), =vulkan den Vulkan-Weg."""
    force = os.environ.get("TUNEBRIDGE_GPU", "").strip().lower()
    if force in ("0", "aus", "off"):
        return "software"
    if force in ("1", "an", "on"):
        return "gpu"
    if force == "vulkan":
        return "vulkan"
    if _gpu_tries() >= 2:
        return "software"          # zweimal hintereinander nie fertig geworden → dauerhaft sicher bleiben
    wayland = bool(os.environ.get("WAYLAND_DISPLAY")) and os.environ.get("QT_QPA_PLATFORM", "") in ("", "wayland")
    if wayland and _nvidia() and _vulkan():
        return "vulkan"
    return "software"


def _qt_env() -> None:
    flags = ["--autoplay-policy=no-user-gesture-required"]
    mode = _gpu_mode()
    if mode == "software":
        flags += ["--disable-gpu", "--disable-gpu-compositing"]
    elif mode == "vulkan":
        os.environ.setdefault("QSG_RHI_BACKEND", "vulkan")
    if mode != "software" and not os.environ.get("TUNEBRIDGE_GPU"):
        try:   # Absturzschutz nur für die automatische Wahl; wird nach erfolgreichem Laden wieder gelöscht
            (osutil.data_dir() / GPU_TRY).write_text(f"{_gpu_tries() + 1} {mode}")
        except OSError:
            pass
    os.environ["TUNEBRIDGE_RENDER"] = mode
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(
        [os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", ""), *flags]).strip()

    # PySide6 (LGPL) statt PyQt6 (GPL) – damit SH-Tunebridge unter eigener Lizenz weitergegeben werden darf
    os.environ.setdefault("QT_API", "pyside6")
