#!/usr/bin/env bash
# Existing portable 3DS checks, without devkitPro, CMake, ROMs, or an emulator.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -f "$ROOT/decomp/include/PR/gbi.h" ]; then
    echo 'Missing decomp headers: git submodule update --init --depth 1 decomp' >&2
    exit 1
fi
TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gdx-host-tests.XXXXXX")"
trap 'rm -rf "$TEST_DIR"' EXIT
"${CC:-cc}" -O1 "$ROOT/port/tests/gfx_pack_tests.c" \
    -I"$ROOT/decomp/include" \
    -DPORT=1 -DGDIFFUSER_PORT=1 -DF3DEX_GBI_2=1 -D_LANGUAGE_C=1 -DVERSION_US=1 \
    -o "$TEST_DIR/gfx_pack_tests"
"${CXX:-c++}" -std=c++20 -O1 "$ROOT/port/tests/gfx_convert_tests.cpp" \
    "$ROOT/port/n64_gfx_convert.cpp" -I"$ROOT/port" -o "$TEST_DIR/gfx_convert_tests"
"${CC:-cc}" -O1 "$ROOT/port/3ds/assets/test/gdx3ds_fs_host_smoke.c" \
    "$ROOT/port/3ds/assets/gdx3ds_fs_sd.c" \
    "$ROOT/port/3ds/assets/zipshim/gdx3ds_zipshim.c" \
    "$ROOT/port/3ds/assets/third_party/miniz/miniz.c" \
    -I"$ROOT/port/3ds/include" -I"$ROOT/port/3ds/lus_stubs" \
    -I"$ROOT/port/3ds/assets/third_party/miniz" -DMINIZ_NO_TIME \
    -o "$TEST_DIR/fs_host_smoke"
cd "$TEST_DIR"
./gfx_pack_tests
./gfx_convert_tests
./fs_host_smoke

python3 -m unittest discover -s "$ROOT/tools/benchmark_3ds" -p 'test_*.py'

python3 -m unittest discover -s "$ROOT/tools/native_assets" -p 'test_*.py'
