#!/usr/bin/env bash
# Isolated Linux toolchain; only this checkout is mounted, with the caller's UID.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${GDX_DEV_IMAGE:-gdx-3ds-dev:local}"
usage() {
    cat <<'TXT'
Usage: bash tools/dev.sh COMMAND [arguments]
  setup             Build/install the pinned Docker development image
  doctor            Print toolchain and dependency versions
  build [--jobs N]  Apply the patch stack, run host tests, build 3DS game + harness
  test              Run portable host tests
  extractor         Build/install the host gdx-extract asset converter
  native-build      Build isolated native M1a mesh harness in build-3ds-native/
  benchmark-build   Build opt-in M0 diagnostics in build-3ds-benchmark/
  cia               Build the CIA (same title ID as upstream; do not install over it)
  run COMMAND ...   Run a command in the development container
  shell             Open a development shell
TXT
}
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 1; }
case "${1:-}" in
    setup)
        exec docker build --tag "$IMAGE" "$ROOT/tools/docker" ;;
    doctor)
        set -- bash -c 'cmake --version | head -1; gcc --version | head -1; "$DEVKITPRO/devkitARM/bin/arm-none-eabi-gcc" --version | head -1; dkp-pacman -Q devkitARM libctru citro3d 3dstools; python3 -c "import yaml, PIL; print(\"Python dependencies available\")"; command -v makerom bannertool' ;;
    build) shift; set -- bash tools/ci-3ds.sh "$@" ;;
    test) set -- bash tools/test-host.sh ;;
    extractor) shift; set -- bash tools/docker/build-extractor.sh "$@" ;;
    native-build) set -- bash tools/docker/build-native.sh ;;
    benchmark-build) set -- bash tools/docker/build-benchmark.sh ;;
    cia) set -- cmake --build build-3ds --target G-Diffuser-3DS-cia --parallel "${GDX_JOBS:-4}" ;;
    run) shift; [ "$#" -gt 0 ] || { usage; exit 2; } ;;
    shell) set -- bash ;;
    -h|--help|'') usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo 'Development image missing. Run: bash tools/dev.sh setup' >&2
    exit 1
fi
TTY=()
if [ -t 0 ] && [ -t 1 ]; then TTY=(-it); fi
exec docker run --rm --init "${TTY[@]}" \
    --user "$(id -u):$(id -g)" \
    --mount "type=bind,source=$ROOT,target=$ROOT" \
    --workdir "$ROOT" --env "GDX_JOBS=${GDX_JOBS:-4}" \
    "$IMAGE" "$@"
