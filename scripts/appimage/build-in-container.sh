#!/usr/bin/env bash
# Läuft im Container ubuntu:22.04. Eingaben: /build (dieser Ordner), /out (Wheels + requirements), VER.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
APPIMAGETOOL_URL=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage
APPIMAGETOOL_SHA=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
RUNTIME_URL=https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64
RUNTIME_SHA=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d
UV_URL=https://github.com/astral-sh/uv/releases/download/0.13.0/uv-x86_64-unknown-linux-musl.tar.gz
UV_SHA=b0828fc4cdc47d65951e94b5f0a15a5364420e8dcd88723f3b21e7a2eb30bbc3

echo "› Pakete"
apt-get update -qq
apt-get install -y -qq --no-install-recommends ca-certificates curl file binutils patchelf pulseaudio-utils openssh-client \
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 >/dev/null

echo "› uv (statisch, Version + Prüfsumme festgelegt)"
curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 -o /tmp/uv.tgz "$UV_URL"; echo "$UV_SHA  /tmp/uv.tgz" | sha256sum -c --quiet
tar -xzf /tmp/uv.tgz -C /tmp && install -m755 /tmp/uv-x86_64-unknown-linux-musl/uv /usr/local/bin/uv

APPDIR=/tmp/AppDir
mkdir -p "$APPDIR/usr"

echo "› Python 3.14 (portabel)"
export UV_PYTHON_INSTALL_DIR=/tmp/py UV_CACHE_DIR=/tmp/uvcache UV_NO_PROGRESS=1
uv python install 3.14 >/dev/null
PYREAL="$(dirname "$(dirname "$(readlink -f "$(uv python find 3.14)")")")"   # echter Ordner, kein Symlink
cp -a "$PYREAL" "$APPDIR/usr/python"
test -x "$APPDIR/usr/python/bin/python3" && test ! -L "$APPDIR/usr/python"
PY="$APPDIR/usr/python/bin/python3"

echo "› Abhängigkeiten (Hash-geprüft aus uv.lock) + SH-Tunebridge"
uv pip install -q --python "$PY" --break-system-packages --require-hashes -r /out/requirements.txt
uv pip install -q --python "$PY" --break-system-packages --no-deps /out/wheels/*.whl

echo "› Verschlanken"
P="$APPDIR/usr/python"
rm -rf "$P"/lib/python3.14/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3} "$P"/lib/{tcl*,tk*,itcl*,thread*} \
       "$P"/include "$P"/share "$P"/lib/pkgconfig "$P"/bin/{idle3*,pydoc3*,2to3*}
SP="$P/lib/python3.14/site-packages"
find "$SP" -type d -name __pycache__ -prune -exec rm -rf {} +
QT="$SP/PySide6"
# Nicht benötigte Qt-Teile (Entwicklerwerkzeuge, 3D, Multimedia …) – Fenster/WebEngine bleiben vollständig
rm -rf "$QT"/{Designer,designer,linguist,lrelease,lupdate,assistant,qmlls,qmlformat,qmllint,qmlscene,qmltestrunner,examples,glue,include,typesystems,scripts,doc}
rm -rf "$QT"/Qt/lib/libQt6{3D,Quick3D,Multimedia,SpatialAudio,Charts,DataVisualization,Graphs,Bluetooth,Nfc,Sensors,SerialPort,SerialBus,Location,PositioningQuick,RemoteObjects,Scxml,StateMachine,TextToSpeech,VirtualKeyboard,Designer,Help,UiTools,Pdf,HttpServer,WebSockets,Test,QuickTest,Sql,QmlLocalStorage,Concurrent,NetworkAuth,ShaderTools,Charts,FFmpegStub}*
rm -f "$QT"/Qt/lib/libav* "$QT"/Qt/lib/libsw*   # FFmpeg von Qt Multimedia – WebEngine hat ein eigenes
rm -rf "$QT"/Qt/plugins/{sceneparsers,renderers,geometryloaders,multimedia,texttospeech,sensors,position,canbus,sqldrivers,designer,qmltooling,assetimporters,renderplugins,geoservices}
rm -rf "$QT"/Qt/qml/{Qt3D,QtQuick3D,QtMultimedia,QtLocation,QtPositioning,QtTest,QtTextToSpeech,QtCharts,QtDataVisualization,QtGraphs,QtSensors,QtScxml,QtRemoteObjects,QtWebSockets,QtNfc,QtBluetooth} "$QT"/Qt/qml/QtQuick/{LocalStorage,VirtualKeyboard,Scene3D,Scene2D}
rm -f "$QT"/QtQuickTest*.abi3.so
rm -f "$QT"/Qt3D*.abi3.so "$QT"/QtQuick3D*.abi3.so "$QT"/QtMultimedia*.abi3.so "$QT"/QtCharts*.abi3.so "$QT"/QtData*.abi3.so \
      "$QT"/QtBluetooth*.abi3.so "$QT"/QtNfc*.abi3.so "$QT"/QtSensors*.abi3.so "$QT"/QtSerial*.abi3.so "$QT"/QtLocation*.abi3.so \
      "$QT"/QtRemote*.abi3.so "$QT"/QtScxml*.abi3.so "$QT"/QtStateMachine*.abi3.so \
      "$QT"/QtTextToSpeech*.abi3.so "$QT"/QtDesigner*.abi3.so "$QT"/QtHelp*.abi3.so "$QT"/QtUiTools*.abi3.so \
      "$QT"/QtPdf*.abi3.so "$QT"/QtHttpServer*.abi3.so "$QT"/QtWebSockets*.abi3.so "$QT"/QtTest*.abi3.so "$QT"/QtSql*.abi3.so \
      "$QT"/QtConcurrent*.abi3.so "$QT"/QtNetworkAuth*.abi3.so "$QT"/QtShaderTools*.abi3.so \
      "$QT"/QtSpatialAudio*.abi3.so "$QT"/QtGraphs*.abi3.so
"$PY" -m compileall -q -j0 "$SP/tunebridge" >/dev/null || true

qtmissing() {  # gibt aus: Datei, wenn ihr eine Qt-Bibliothek fehlt
  for f in "$@"; do
    for n in $(readelf -d "$f" 2>/dev/null | grep -oE 'libQt6[A-Za-z0-9-]*\.so\.[0-9]+' | sort -u); do
      [ -e "$QT/Qt/lib/$n" ] || { echo "$f"; break; }
    done
  done
}
echo "› Verwaiste optionale Qt-Erweiterungen entfernen (Plugins/QML ohne ihre Basis)"
while :; do
  ORPH=$(qtmissing $(find "$QT/Qt/plugins" "$QT/Qt/qml" -name '*.so' -type f))
  [ -z "$ORPH" ] && break
  echo "$ORPH" | xargs rm -f
done
find "$QT/Qt/qml" -type d -empty -delete
echo "› Prüfen: Kernteile vollständig"
CORE=$(qtmissing $(find "$QT/Qt/lib" -name 'libQt6*.so.6' -type f) "$QT/Qt/libexec/QtWebEngineProcess" "$QT"/*.abi3.so)
if [ -n "$CORE" ]; then
  # Bibliotheken, deren Basis wir bewusst entfernt haben und die nichts Wichtiges braucht -> ebenfalls weg
  for f in $CORE; do case "$(basename "$f")" in
    QtWebEngine*|libQt6WebEngine*|libQt6Widgets*|libQt6Gui*|libQt6Core*|libQt6Network*|libQt6WebChannel*|libQt6Quick.so*|libQt6Qml.so*|QtWidgets*|QtGui*|QtCore*|QtNetwork*|QtWebChannel*|QtWebEngineProcess)
      echo "FEHLT in Kernteil: $f"; exit 1;;
    *) rm -f "$f";;
  esac; done
  CORE=$(qtmissing $(find "$QT/Qt/lib" -name 'libQt6*.so.6' -type f) "$QT/Qt/libexec/QtWebEngineProcess" "$QT"/*.abi3.so)
  [ -z "$CORE" ] || { echo "FEHLT:"; echo "$CORE"; exit 1; }
fi

echo "› Häufig fehlende Qt-Hilfsbibliotheken neben Qt ablegen (kein globales LD_LIBRARY_PATH)"
for l in libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-image.so.0 libxcb-keysyms.so.1 libxcb-render-util.so.0 \
         libxcb-util.so.1 libxcb-xkb.so.1 libxkbcommon-x11.so.0; do
  cp -L "/usr/lib/x86_64-linux-gnu/$l" "$QT/Qt/lib/"
  patchelf --set-rpath '$ORIGIN' "$QT/Qt/lib/$l"   # eigene Abhängigkeiten im selben Ordner finden
done

echo "› Ersatz-Werkzeuge: parecord/parec/pactl (PulseAudio/PipeWire), ssh-keygen (Update-Signatur)"
FB="$APPDIR/usr/fallback"; mkdir -p "$FB/bin" "$FB/libexec" "$FB/lib"
cp -L /usr/bin/pacat /usr/bin/pactl /usr/bin/ssh-keygen "$FB/libexec/"
ln -s pacat "$FB/libexec/parecord"; ln -s pacat "$FB/libexec/parec"
for b in parecord parec pactl ssh-keygen; do cp /build/tool-wrapper "$FB/bin/$b"; done
for f in "$FB"/libexec/pacat "$FB"/libexec/pactl "$FB"/libexec/ssh-keygen; do ldd "$f"; done \
  | awk '/=> \//{print $3}' | sort -u \
  | grep -v -E '/(libc|libm|libdl|libpthread|librt|libresolv|ld-linux-x86-64)\.so' \
  | while read -r l; do cp -L "$l" "$FB/lib/"; done
echo "› Lizenztexte aller mitgelieferten Systemteile"
L="$APPDIR/usr/share/licenses"; mkdir -p "$L"
for f in /usr/bin/pacat /usr/bin/pactl /usr/bin/ssh-keygen $(ls "$FB"/lib) $(cd "$QT/Qt/lib" && ls libxcb-*.so* libxkbcommon-x11.so* 2>/dev/null); do
  case "$f" in /*) q="$f";; *) q="$(basename "$f")";; esac
  dpkg -S "$q" 2>/dev/null | head -1 | cut -d: -f1
done | sort -u | while read -r pkg; do
  [ -f "/usr/share/doc/$pkg/copyright" ] && cp "/usr/share/doc/$pkg/copyright" "$L/$pkg.txt"
done
cp "$P/lib/python3.14/LICENSE.txt" "$L/python.txt" 2>/dev/null || true
ls "$L" | wc -l | xargs echo "  Lizenzdateien:"

echo "› AppDir"
cp /build/AppRun "$APPDIR/AppRun"
cp /build/sh-tunebridge.desktop "$APPDIR/"
cp "$SP/tunebridge/web/static/icon.svg" "$APPDIR/sh-tunebridge.svg"
ln -s sh-tunebridge.svg "$APPDIR/.DirIcon"

echo "› appimagetool (Version + Prüfsumme festgelegt)"
curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 -o /tmp/appimagetool "$APPIMAGETOOL_URL"; echo "$APPIMAGETOOL_SHA  /tmp/appimagetool" | sha256sum -c --quiet
curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 -o /tmp/runtime "$RUNTIME_URL";           echo "$RUNTIME_SHA  /tmp/runtime" | sha256sum -c --quiet
chmod +x /tmp/appimagetool
OUTFILE="/out/SH-Tunebridge-$VER-x86_64.AppImage"
ARCH=x86_64 /tmp/appimagetool --appimage-extract-and-run --runtime-file /tmp/runtime --no-appstream \
  "$APPDIR" "$OUTFILE" >/tmp/appimagetool.log 2>&1 || { tail -30 /tmp/appimagetool.log; exit 1; }
chown "$HOST_UID:$HOST_GID" -R /out
echo "✓ $(basename "$OUTFILE") – $(du -h "$OUTFILE" | cut -f1)"
