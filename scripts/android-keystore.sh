#!/usr/bin/env bash
# Einmalig: Release-Schlüssel der Android-App anlegen. Führst DU selbst aus (fragt Passwort und Namen ab):
#   ./scripts/android-keystore.sh [Ordner]      Standard-Ordner: /mnt/work/keys/sh-tunebridge-android
# Der Schlüssel liegt außerhalb des Repos und kommt nie in die CI. SOFORT offline sichern (z. B. USB-Stick + Ausdruck
# der Passwörter): Geht er verloren, kann die App nie wieder aktualisiert werden – Android nimmt Updates nur mit
# demselben Schlüssel an.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:-/mnt/work/keys/sh-tunebridge-android}"
JKS="$DIR/sh-tunebridge-release.jks"
[[ -e "$JKS" ]] && { echo "Gibt es schon: $JKS – nichts überschrieben."; exit 1; }
mkdir -p "$DIR" && chmod 700 "$DIR"
docker image inspect tunebridge-android >/dev/null 2>&1 || docker build -t tunebridge-android android/docker
echo "Lege den Schlüssel an. Gültigkeit 30 Jahre, RSA 4096. Passwort gut merken."
docker run --rm -it -u "$(id -u):$(id -g)" -v "$DIR:/keys" tunebridge-android \
  keytool -genkeypair -v -keystore /keys/sh-tunebridge-release.jks -alias sh-tunebridge \
  -keyalg RSA -keysize 4096 -validity 10950 -storetype PKCS12
chmod 600 "$JKS"
cat > android/keystore.properties <<PROPS
# Nicht im Repo (android/.gitignore). Passwörter stehen hier NICHT – publish-android.sh fragt sie ab.
storeFile=/keys/sh-tunebridge-release.jks
keyAlias=sh-tunebridge
PROPS
echo "Fingerabdruck (zum Notieren; fragt nochmal nach dem Passwort):"
docker run --rm -it -u "$(id -u):$(id -g)" -v "$DIR:/keys:ro" tunebridge-android \
  keytool -list -v -keystore /keys/sh-tunebridge-release.jks -alias sh-tunebridge | grep -E "SHA256:" || true
echo
echo "Fertig: $JKS"
echo "Jetzt offline sichern! Danach Releases mit: TUNEBRIDGE_ANDROID_KEYS=$DIR ./scripts/publish-android.sh X.Y.Z"
