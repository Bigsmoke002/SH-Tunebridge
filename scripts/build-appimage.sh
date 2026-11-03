#!/usr/bin/env bash
# SH-Tunebridge als AppImage bauen (x86_64). Braucht Docker (ohne sudo) und uv auf dem Bau-Rechner.
# Gebaut wird in ubuntu:22.04 -> läuft auf praktisch allen Desktop-Distributionen ab ~2022.
# Ergebnis: build/appimage/SH-Tunebridge-<version>-x86_64.AppImage
set -euo pipefail
cd "$(dirname "$0")/.."
VER=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)
OUT=build/appimage
rm -rf "$OUT"; mkdir -p "$OUT/wheels"
uv build --wheel -q -o "$OUT/wheels"
uv export --frozen --no-dev --extra desktop --no-emit-project --format requirements-txt -q -o "$OUT/requirements.txt"
docker run --rm \
  -v "$PWD/scripts/appimage:/build:ro" -v "$PWD/$OUT:/out" \
  -e VER="$VER" -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  ubuntu:22.04 bash /build/build-in-container.sh
rm -rf "$OUT/wheels" "$OUT/requirements.txt"
ls -la "$OUT"
