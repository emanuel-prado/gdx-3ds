#!/usr/bin/env bash
# Official Linux x86_64 release, checksum supplied by GitHub release metadata.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/tools/3ds-bin/azahar-2126.2.AppImage"
EXPECTED=af037f8b775198f636b14bcfe63fb401b02246ebfefe1025bb905ce042556960
verify() { printf '%s  %s\n' "$EXPECTED" "$1" | sha256sum --check --status; }
mkdir -p "$ROOT/tools/3ds-bin"
if [ -f "$DEST" ] && verify "$DEST"; then
    chmod +x "$DEST"
    echo 'Azahar 2126.2 already installed and verified.'
    exit 0
fi
DOWNLOAD="$(mktemp "$ROOT/tools/3ds-bin/azahar-download.XXXXXX")"
trap 'rm -f "$DOWNLOAD"' EXIT
curl --fail --location --retry 3 \
    https://github.com/azahar-emu/azahar/releases/download/2126.2/azahar.AppImage \
    --output "$DOWNLOAD"
verify "$DOWNLOAD" || { echo 'Azahar checksum mismatch.' >&2; exit 1; }
chmod +x "$DOWNLOAD"
mv "$DOWNLOAD" "$DEST"
echo 'Azahar 2126.2 installed. Launch with: bash tools/azahar.sh'
