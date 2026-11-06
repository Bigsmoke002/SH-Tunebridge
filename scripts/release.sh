#!/usr/bin/env bash
# Neue Version veröffentlichen: ./scripts/release.sh 0.2.0 "Kurzbeschreibung" ["weitere Zeilen…"]
# Erhöht die Version, testet, committet, legt einen SIGNIERTEN Tag an und pusht beides.
# Nur signierte Tags werden vom Updater installiert.
set -euo pipefail
cd "$(dirname "$0")/.."
VER="${1:?Version fehlt, z.B. 0.2.0}"; SUBJ="${2:?Kurzbeschreibung fehlt}"; shift 2
[[ "$VER" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Version muss X.Y.Z sein"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "Arbeitsverzeichnis nicht sauber – erst committen."; exit 1; }
[[ "$(git branch --show-current)" == "main" ]] || { echo "Releases nur von main."; exit 1; }
git rev-parse -q --verify "refs/tags/v$VER" >/dev/null && { echo "v$VER existiert schon"; exit 1; }

uv run pytest -q
sed -i "s/^version = \".*\"/version = \"$VER\"/" pyproject.toml
uv lock -q
sed -i "s/^## Unveröffentlicht ($VER)$/## $VER – $(date +%F)/" CHANGELOG.md
git commit -qam "Release v$VER"
MSG="$SUBJ"$'\n'; for line in "$@"; do MSG+=$'\n'"- $line"; done
git tag -s "v$VER" -m "$MSG"
git verify-tag "v$VER"
git push origin main "v$VER"
echo "Veröffentlicht: v$VER – Nutzer sehen das Update beim nächsten Check (spätestens nach 6 h)."
if command -v docker >/dev/null && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  ./scripts/publish-appimage.sh "$VER"
else
  echo "Hinweis: AppImage nicht gebaut (Docker/github-cli fehlt oder nicht angemeldet) – später: ./scripts/publish-appimage.sh $VER"
fi
