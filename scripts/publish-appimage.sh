#!/usr/bin/env bash
# AppImage für einen signierten Release-Tag bauen, Manifest signieren und als GitHub-Release hochladen.
#   ./scripts/publish-appimage.sh [X.Y.Z]   (Standard: Version aus pyproject.toml)
# Voraussetzungen: Docker (ohne sudo), github-cli angemeldet (gh auth login), sauberer Stand genau auf dem Tag.
set -euo pipefail
cd "$(dirname "$0")/.."
VER="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)}"
TAG="v$VER"
REPO="Bigsmoke002/SH-Tunebridge"
NS="sh-tunebridge-release"

git verify-tag "$TAG" >/dev/null 2>&1 || { echo "Tag $TAG fehlt oder ist nicht gültig signiert."; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "Arbeitsverzeichnis nicht sauber."; exit 1; }
[[ "$(git rev-parse HEAD)" == "$(git rev-parse "$TAG^{commit}")" ]] || { echo "Gebaut wird nur genau der Stand von $TAG (git checkout $TAG)."; exit 1; }
command -v gh >/dev/null || { echo "github-cli fehlt (sudo pacman -S github-cli)."; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "github-cli ist nicht angemeldet (gh auth login)."; exit 1; }

./scripts/build-appimage.sh
D=build/appimage
F="SH-Tunebridge-$VER-x86_64.AppImage"
M="SH-Tunebridge-$VER.manifest"
NOTES=$(git tag -l --format='%(contents)' "$TAG" | sed '/-----BEGIN SSH SIGNATURE-----/,$d')
{
  echo "SH-Tunebridge-Release 1"
  echo "version=$VER"
  echo "file=$F"
  echo "size=$(stat -c%s "$D/$F")"
  echo "sha256=$(sha256sum "$D/$F" | cut -d' ' -f1)"
  echo
  printf '%s\n' "$NOTES"
} > "$D/$M"
KEY=$(git config user.signingkey); KEY="${KEY%.pub}"
rm -f "$D/$M.sig"
ssh-keygen -q -Y sign -f "$KEY" -n "$NS" "$D/$M"
ssh-keygen -Y verify -f src/tunebridge/release_signers -I sh-tunebridge -n "$NS" -s "$D/$M.sig" < "$D/$M"

if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  gh release upload "$TAG" "$D/$F" "$D/$M" "$D/$M.sig" --clobber -R "$REPO"
else
  gh release create "$TAG" "$D/$F" "$D/$M" "$D/$M.sig" -R "$REPO" --verify-tag \
    --title "SH-Tunebridge $VER" --notes "$NOTES

**Installation:** \`$F\` herunterladen → Rechtsklick → Eigenschaften → „Als Programm ausführen“ erlauben → starten.
Oder im Terminal: \`chmod +x $F && ./$F\`. Updates kommen danach automatisch."
fi
echo "✓ AppImage $VER veröffentlicht: https://github.com/$REPO/releases/tag/$TAG"
