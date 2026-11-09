#!/usr/bin/env bash
# Android-App im Build-Container bauen (das SDK und Gradle liegen nur dort; der Wrapper ist für die CI).
#   scripts/android-build.sh                 -> Debug-APK + Tests
#   scripts/android-build.sh assembleRelease -> signiertes Release (braucht android/keystore.properties)
#   scripts/android-build.sh install         -> Debug-APK bauen und per adb aufs Handy
set -euo pipefail
cd "$(dirname "$0")/.."
CACHE="${TUNEBRIDGE_ANDROID_CACHE:-/mnt/work/caches/tunebridge-android}"
mkdir -p "$CACHE/gradle" "$CACHE/home"
docker image inspect tunebridge-android >/dev/null 2>&1 || docker build -t tunebridge-android android/docker
install=0
if [[ "${1:-}" == "install" ]]; then install=1; set -- ; fi
tasks=("${@:-testDebugUnitTest assembleDebug}")
# Release-Schlüssel (nur für assembleRelease): Ordner außerhalb des Repos, nur lesend als /keys eingebunden
KEYS=()
if [[ -n "${TUNEBRIDGE_ANDROID_KEYS:-}" ]]; then
  KEYS=(-v "$TUNEBRIDGE_ANDROID_KEYS:/keys:ro" -e TB_STORE_PASSWORD -e TB_KEY_PASSWORD)
fi
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/cache/home -e GRADLE_USER_HOME=/cache/gradle \
  -e ANDROID_USER_HOME=/cache/home/.android "${KEYS[@]}" \
  -v "$PWD:/src" -v "$CACHE:/cache" -w /src/android tunebridge-android \
  bash -c "gradle --no-daemon --console=plain ${tasks[*]}"
if (( install )); then
  apk=android/app/build/outputs/apk/debug/app-debug.apk
  # Mehrere Handys (USB und WLAN-adb): auf jedes verbundene installieren
  for d in $(adb devices | awk 'NR>1 && $2=="device" {print $1}'); do
    echo "→ $d"
    adb -s "$d" install -r "$apk"
    adb -s "$d" shell monkey -p de.bs002.tunebridge.dev -c android.intent.category.LAUNCHER 1 >/dev/null
  done
fi
