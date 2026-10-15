#!/usr/bin/env bash
set -euo pipefail
cmake -S torch -B build-extract \
    -DUSE_STANDALONE=ON -DBUILD_STORMLIB=OFF -DGDX_DETERMINISTIC=ON \
    -DGDX_OUTPUT_NAME=gdx-extract -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_DEFAULT_CMP0091=NEW "$@"
cmake --build build-extract --parallel "${GDX_JOBS:-4}"
cmake --install build-extract --prefix "$PWD/build-extract/install"
