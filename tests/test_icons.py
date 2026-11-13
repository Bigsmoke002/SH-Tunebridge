"""Symbole: PC und Handy werden aus scripts/gen-icons.py erzeugt und müssen aktuell sein; jedes benutzte Symbol existiert."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_generated_icons_up_to_date():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/gen-icons.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_used_icon_exists():
    js = (ROOT / "src/tunebridge/web/static/app.js").read_text(encoding="utf-8")
    html = (ROOT / "src/tunebridge/web/index.html").read_text(encoding="utf-8")
    block = js[js.index("const ICONS = {"):js.index("/* ICONS:END */")]
    have = set(re.findall(r"^  (\w+):", block, re.M))
    used = set(re.findall(r'icon\("(\w+)"', js)) | set(re.findall(r'data-icon="(\w+)"', html + js)) | set(re.findall(r'icon: "(\w+)"', js))
    assert not used - have, used - have
    kt = (ROOT / "android/app/src/main/java/de/bs002/tunebridge/ui/theme/Icons.kt").read_text(encoding="utf-8")
    defined = set(re.findall(r"^    ([A-Z]\w*)\(", kt, re.M))
    usedk = {m for f in (ROOT / "android/app/src/main/java").rglob("*.kt") for m in re.findall(r"Ico\.([A-Z]\w*)", f.read_text(encoding="utf-8"))}
    assert not usedk - defined, usedk - defined
