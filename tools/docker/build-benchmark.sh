#!/usr/bin/env bash
set -euo pipefail
cmake -S . -B build-3ds-benchmark \
    -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" \
    -DGDX_PLATFORM_3DS=ON -DGDX3DS_BENCHMARK=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build-3ds-benchmark --target G-Diffuser-3DS_3dsx --parallel "${GDX_JOBS:-4}"
