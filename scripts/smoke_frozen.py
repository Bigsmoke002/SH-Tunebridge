"""Rauchtest für das fertige Programm (CI auf Windows/macOS): Server starten, Oberfläche + API abfragen.
Aufruf: python scripts/smoke_frozen.py <Pfad zur ausführbaren Datei>"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

exe = sys.argv[1]
port = "8799"
env = {**os.environ, "TUNEBRIDGE_DATA": tempfile.mkdtemp(prefix="tb-smoke-")}
p = subprocess.Popen([exe, "ui", "--port", port, "--no-browser"], env=env)
try:
    for _ in range(120):
        try:
            html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read().decode("utf-8")
            break
        except OSError:
            time.sleep(0.5)
    else:
        sys.exit("Server startet nicht")
    assert "SH-Tunebridge" in html
    for path in ("/static/app.js", "/static/icon.svg"):
        assert urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5).status == 200, path
    cons = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/consent", timeout=5))
    assert cons["needs_onboarding"] and not any(cons["server"].values()), cons   # nichts vorab angehakt
    upd = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/update", timeout=30))
    assert upd["kind"] in ("frozen", "download"), upd      # frozen = tauscht sich selbst aus, download = nur Datei laden
    src = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/sources", timeout=15))
    print("Audioquellen:", src)
    print("Rauchtest OK")
finally:
    p.terminate()
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()

# Zweiter Teil: so starten wie per Doppelklick (App-Fenster). Der Server-Test oben fängt Abstürze im
# Fenster-Teil nicht ab (v0.6.0: Windows-Fenster stürzte wegen .svg-Symbol sofort ab).
app_port = "8797"
env2 = {**os.environ, "TUNEBRIDGE_DATA": tempfile.mkdtemp(prefix="tb-smoke-app-"), "TUNEBRIDGE_APP_PORT": app_port,
        "TUNEBRIDGE_NO_AUTOSYNC": "1"}
q = subprocess.Popen([exe], env=env2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{app_port}/", timeout=2)
            break
        except OSError:
            if q.poll() is not None:
                break
            time.sleep(0.5)
    time.sleep(20)                     # Fenster aufbauen lassen
    if q.poll() is not None:
        out = q.stdout.read().decode("utf-8", "replace")[-4000:]
        sys.exit(f"App-Fenster beendet sich sofort (Code {q.returncode}):\n{out}")
    print("App-Fenster läuft – Rauchtest Fenster OK")
finally:
    q.kill()
    try:
        q.wait(10)
    except subprocess.TimeoutExpired:
        pass
