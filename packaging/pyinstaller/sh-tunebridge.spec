# PyInstaller-Rezept für Windows und macOS.  Bauen:  uv run pyinstaller packaging/pyinstaller/sh-tunebridge.spec
# Ergebnis: dist/SH-Tunebridge/ (Windows) bzw. dist/SH-Tunebridge.app (macOS)
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parents[1]
VERSION = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
ICON = str(ROOT / "assets/logo/logo-256.png")   # wird von PyInstaller (mit Pillow) nach .ico/.icns umgewandelt

datas = collect_data_files("tunebridge", excludes=["**/__pycache__/**"])
datas += [(str(ROOT / "LICENSE"), "."), (str(ROOT / "THIRD_PARTY.md"), "."), (str(ROOT / "DATENSCHUTZ.md"), ".")]
hidden = collect_submodules("tunebridge") + collect_submodules("uvicorn") + ["soundcard", "webview"]

a = Analysis([str(Path(SPECPATH) / "entry.py")], pathex=[str(ROOT / "src")], datas=datas, hiddenimports=hidden,
             excludes=["tkinter", "PySide6", "PyQt5", "PyQt6", "pytest", "IPython"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SH-Tunebridge", icon=ICON,
          console=False, upx=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SH-Tunebridge", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(coll, name="SH-Tunebridge.app", icon=ICON, bundle_identifier="de.smokes-hub.tunebridge",
                 version=VERSION, info_plist={
                     "CFBundleShortVersionString": VERSION, "NSHighResolutionCapable": True,
                     "LSApplicationCategoryType": "public.app-category.music",
                     "NSMicrophoneUsageDescription": "SH-Tunebridge hört nur auf deinen Klick kurz zu, um einen Song "
                                                     "zu erkennen. Aufnahmen werden nicht gespeichert.",
                 })
