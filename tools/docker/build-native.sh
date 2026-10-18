#!/usr/bin/env bash
set -euo pipefail
cmake -S port/3ds/native -B build-3ds-native \
    -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" -DCMAKE_BUILD_TYPE=Release
cmake --build build-3ds-native --parallel "${GDX_JOBS:-4}"
dkp-pacman -Q devkitARM libctru citro3d 3dstools > build-3ds-native/toolchain.txt
sha256sum build-3ds-native/gdx-native-m1a.3dsx build-3ds-native/gdx-native-m1a.elf \
    build-3ds-native/gdx-native-swatch.3dsx build-3ds-native/gdx-native-swatch.elf > build-3ds-native/SHA256SUMS
