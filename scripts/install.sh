#!/usr/bin/env bash
# SH-Tunebridge auf einem (weiteren) Linux-Rechner installieren – ohne sudo.
# Aufruf:  ./scripts/install.sh            (aus dem Projektordner, editierbar)
#          ./scripts/install.sh <git-url>  (direkt aus dem Repo)
set -euo pipefail
SRC="${1:-$(cd "$(dirname "$0")/.." && pwd)}"

need() { command -v "$1" >/dev/null || { echo "FEHLT: $1 – $2"; MISSING=1; }; }
MISSING=0
need uv       "Arch/CachyOS: sudo pacman -S uv   | Debian/Ubuntu: pipx install uv"
need parecord "Arch: sudo pacman -S libpulse     | Debian/Ubuntu: sudo apt install pulseaudio-utils"
need pactl    "wie parecord"
[ "$MISSING" = 0 ] || exit 1
command -v ffmpeg >/dev/null || echo "HINWEIS: ffmpeg fehlt – Apple/Shazam-Hörproben (AAC) laufen dann nicht im App-Fenster. Arch: sudo pacman -S ffmpeg"

if [[ -d "$SRC" ]]; then
  uv tool install --force --editable "$SRC[desktop]"
else
  TAG=$(git ls-remote --tags --refs "$SRC" | awk -F/ '{print $NF}' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
  [ -n "$TAG" ] || { echo "Keine Release-Version im Repo gefunden"; exit 1; }
  echo "Installiere $TAG …"
  uv tool install --force "tunebridge[desktop] @ git+$SRC@$TAG"
fi

tunebridge setup

ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
mkdir -p "$ICONS"
"$HOME/.local/share/uv/tools/tunebridge/bin/python" -c "from importlib.resources import files; print(files('tunebridge.web')/'static'/'icon.svg')" \
  | xargs -I{} cp {} "$ICONS/tunebridge.svg"

APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
cat > "$APPS/tunebridge.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=SH-Tunebridge
Comment=Songs erkennen, reinhören und nach Genre einsortieren
Exec=$HOME/.local/bin/tunebridge app
StartupWMClass=tunebridge
Icon=tunebridge
Terminal=false
Categories=AudioVideo;Audio;
DESK
echo "Fertig. Starten: 'tunebridge ui' oder über das Startmenü (SH-Tunebridge)."
