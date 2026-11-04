#!/usr/bin/env bash
# Windows-/macOS-Pakete eines Release-Tags von GitHub Actions holen, Manifeste signieren und zum Release hochladen.
#   ./scripts/publish-platforms.sh [X.Y.Z]
# Ablauf: Tag pushen → Workflow „build“ läuft (Tests + Bau auf echten Windows-/Mac-Rechnern) → dieses Skript.
# Signiert wird nur hier lokal mit dem Release-Schlüssel – der Schlüssel kommt nie zu GitHub.
set -euo pipefail
cd "$(dirname "$0")/.."
VER="${1:-$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)}"
TAG="v$VER"
REPO="Bigsmoke002/SH-Tunebridge"
NS="sh-tunebridge-release"
gh auth status >/dev/null 2>&1 || { echo "github-cli ist nicht angemeldet (gh auth login)."; exit 1; }
SHA=$(git rev-parse "$TAG^{commit}")
RUN=$(gh run list -R "$REPO" -w build --json databaseId,headSha,conclusion \
      -q "map(select(.headSha==\"$SHA\" and .conclusion==\"success\"))[0].databaseId")
[[ -n "$RUN" && "$RUN" != null ]] || { echo "Kein erfolgreicher Build-Lauf für $TAG gefunden."; exit 1; }
D=build/platforms; rm -rf "$D"; mkdir -p "$D"
gh run download "$RUN" -R "$REPO" -D "$D"
NOTES=$(git tag -l --format='%(contents)' "$TAG" | sed '/-----BEGIN SSH SIGNATURE-----/,$d')
KEY=$(git config user.signingkey); KEY="${KEY%.pub}"
UP=()
for spec in "windows:SH-Tunebridge-$VER-windows-x64.zip" "macos:SH-Tunebridge-$VER-macos-arm64.dmg"; do
  T="${spec%%:*}"; F="${spec#*:}"; P="$D/SH-Tunebridge-$T/$F"
  [[ -f "$P" ]] || { echo "Fehlt: $P"; exit 1; }
  (cd "$(dirname "$P")" && sha256sum -c --ignore-missing "SHA256SUMS-$T.txt")
  M="$D/SH-Tunebridge-$VER-$T.manifest"
  { echo "SH-Tunebridge-Release 1"; echo "version=$VER"; echo "file=$F"
    echo "size=$(stat -c%s "$P")"; echo "sha256=$(sha256sum "$P" | cut -d' ' -f1)"; echo; printf '%s\n' "$NOTES"; } > "$M"
  ssh-keygen -q -Y sign -f "$KEY" -n "$NS" "$M"
  ssh-keygen -Y verify -f src/tunebridge/release_signers -I sh-tunebridge -n "$NS" -s "$M.sig" < "$M"
  UP+=("$P" "$M" "$M.sig")
done
# Windows-Installer (für die Erstinstallation; der Updater nimmt weiter das .zip): Prüfsumme + signiertes Manifest
SETUP="$D/SH-Tunebridge-windows/SH-Tunebridge-$VER-windows-setup.exe"
[[ -f "$SETUP" ]] || { echo "Fehlt: $SETUP"; exit 1; }
(cd "$(dirname "$SETUP")" && sha256sum -c --ignore-missing "SHA256SUMS-windows.txt")
SM="$D/SH-Tunebridge-$VER-windows-setup.manifest"
{ echo "SH-Tunebridge-Release 1"; echo "version=$VER"; echo "file=$(basename "$SETUP")"
  echo "size=$(stat -c%s "$SETUP")"; echo "sha256=$(sha256sum "$SETUP" | cut -d' ' -f1)"; echo; printf '%s\n' "$NOTES"; } > "$SM"
ssh-keygen -q -Y sign -f "$KEY" -n "$NS" "$SM"
UP+=("$SETUP" "$SM" "$SM.sig")
gh release upload "$TAG" "${UP[@]}" --clobber -R "$REPO"
echo "✓ Windows/macOS $VER hochgeladen: https://github.com/$REPO/releases/tag/$TAG"
