"""Startpunkt der fertigen Windows-/macOS-Programme: ohne Argumente öffnet sich das App-Fenster."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    import os
    for name in ("stdout", "stderr"):  # Fenster-Programm ohne Konsole: Ausgaben ins Leere statt Absturz
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    if len(sys.argv) == 1 or sys.argv[1].startswith("-psn_"):  # macOS übergibt beim Doppelklick evtl. -psn_…
        sys.argv = [sys.argv[0], "app"]
    if len(sys.argv) >= 2 and sys.argv[1] == "companion":   # Tray/Schwebe-Icon: schlank starten, ohne die ganze CLI
        from tunebridge.companion import main
        port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8765"
        main(int(port))
        sys.exit(0)
    from tunebridge.cli import app
    app()
