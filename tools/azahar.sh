#!/usr/bin/env bash
# Host GUI, isolated from personal emulator settings/saves; no FUSE required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPIMAGE="$ROOT/tools/3ds-bin/azahar-2126.2.AppImage"
PROFILE="${GDX_AZAHAR_PROFILE:-$ROOT/experiments/local/azahar}"
if [ ! -x "$APPIMAGE" ]; then
    echo "Missing Azahar 2126.2 AppImage: see docs/LOCAL-SETUP.md" >&2
    exit 1
fi
mkdir -p "$PROFILE/data" "$PROFILE/config" "$PROFILE/cache"
ARGS=()
for arg in "$@"; do
    if [ -f "$arg" ]; then arg="$(realpath "$arg")"; fi
    ARGS+=("$arg")
done
# A user/ directory in the calling CWD can override Azahar's XDG paths.
cd "$PROFILE"
exec env APPIMAGE_EXTRACT_AND_RUN=1 \
    XDG_DATA_HOME="$PROFILE/data" XDG_CONFIG_HOME="$PROFILE/config" \
    XDG_CACHE_HOME="$PROFILE/cache" "$APPIMAGE" "${ARGS[@]}"
