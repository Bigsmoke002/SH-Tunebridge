#!/usr/bin/env bash
# Android-App für einen signierten Release-Tag bauen, APK-Manifest mit dem Release-Schlüssel signieren und an das
# GitHub-Release hängen. Die App lädt Updates nur, wenn das Manifest gültig signiert ist und SHA-256 passt.
#   TUNEBRIDGE_ANDROID_KEYS=/mnt/work/keys/sh-tunebridge-android ./scripts/publish-android.sh [X.Y.Z]
# Voraussetzungen: scripts/android-keystore.sh einmal ausgeführt, Docker, github-cli angemeldet, Stand genau auf dem Tag.
set -euo pipefail
cd "$(dirname "$0")/.."
VER="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)}"
TAG="v$VER"
REPO="Bigsmoke002/SH-Tunebridge"
NS="sh-tunebridge-release"
: "${TUNEBRIDGE_ANDROID_KEYS:?Ordner mit dem App-Schlüssel fehlt (TUNEBRIDGE_ANDROID_KEYS=…)}"
[[ -f android/keystore.properties ]] || { echo "android/keystore.properties fehlt – erst scripts/android-keystore.sh"; exit 1; }
git verify-tag "$TAG" >/dev/null 2>&1 || { echo "Tag $TAG fehlt oder ist nicht gültig signiert."; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "Arbeitsverzeichnis nicht sauber."; exit 1; }
[[ "$(git rev-parse HEAD)" == "$(git rev-parse "$TAG^{commit}")" ]] || { echo "Gebaut wird nur genau der Stand von $TAG."; exit 1; }
command -v gh >/dev/null && gh auth status >/dev/null 2>&1 || { echo "github-cli fehlt oder ist nicht angemeldet."; exit 1; }

if [[ -z "${TB_STORE_PASSWORD:-}" ]]; then read -rsp "Passwort des App-Schlüssels: " TB_STORE_PASSWORD; echo; fi
export TB_STORE_PASSWORD TUNEBRIDGE_ANDROID_KEYS
./scripts/android-build.sh testDebugUnitTest assembleRelease
unset TB_STORE_PASSWORD

D=build/android; mkdir -p "$D"
F="SH-Tunebridge-$VER.apk"
M="SH-Tunebridge-$VER-android.manifest"
cp android/app/build/outputs/apk/release/app-release.apk "$D/$F"
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
  gh release create "$TAG" "$D/$F" "$D/$M" "$D/$M.sig" -R "$REPO" --verify-tag --title "$TAG" --notes "$NOTES"
fi
echo "Android-App $VER veröffentlicht. Vorher Pflicht: Test auf einem echten Handy per adb (CLAUDE.md)."
