# Local Linux development environment

Installed for this checkout on 2026-10-14. The host is Zorin OS 18.1 (Ubuntu
24.04 family), x86_64. Docker hosts the build toolchain; Azahar runs on the host.
System packages and shell startup files are unchanged. Build commands mount only
this checkout and run as the invoking user's UID/GID, so outputs stay user-owned.
ROMs, builds, generated assets and emulator data are ignored by Git.

## Installed components

| Component | Version / location |
|---|---|
| Official devkitPro ARM base | `devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5` |
| Project Docker image | `gdx-3ds-dev:local`; recipe in `tools/docker/Dockerfile` |
| devkitARM / cross GCC | r68-1 / 16.1.0 |
| libctru / citro3d / 3dstools | 2.7.0-1 / 1.7.1-2 / 1.3.1-3 |
| CMake / host GCC in container | 3.31.6 / 12.2.0 |
| Python support | Python 3, PyYAML, Pillow |
| Packaging | makerom 0.19.0 and bannertool 1.2.3, built from source in the image |
| Debug/deploy utilities | `arm-none-eabi-gdb`, `arm-none-eabi-addr2line`, `3dslink`, picasso |
| Azahar | Official 2126.2 Linux AppImage in ignored `tools/3ds-bin/` |
| Source dependencies | All submodules initialized recursively at the repository's pinned commits |

The Docker base is pinned. Debian build packages are resolved when the image is
rebuilt; archive the local image if an identical binary environment is needed.
`tools/ci-3ds.sh` applies the tracked 38 libultraship and 10 decomp patches;
those submodule working trees will therefore appear modified. Keep the submodule
commit pointers pinned and record new source deltas as patches.

## Verification completed

- Clean toolchain configure and game `.3dsx` / `.elf` build passed.
- All three existing portable host test suites passed.
- CIA generation with source-built makerom/bannertool passed; no CIA was installed.
- Asset extractor compiled, installed and ran `--help` directly on the host, with
  all dynamic libraries resolving. No ROM was needed or converted.
- Azahar completed all nine graphics harness scenes and the existing BMP pixel
  checker reported `ALL CHECKS PASSED`. The repaired harness supplies storage for
  its logger's missing TLS flag; before that fix its first run logged invalid
  memory reads. The successful run had no unmapped-memory or fatal log entries.
- Cross GDB 14.1 and addr2line are available. Reference ELF section sizes:
  text 2,766,184 bytes; data 172,020 bytes; BSS 7,029,580 bytes. This is image
  section accounting, not total runtime memory usage.

The supplied USA rev0 ROM subsequently passed extraction's golden checksum gate.
A 55-second emulator boot advanced to frame 2675 with no fatal entries. With the
user-supplied `dspfirm.cdc` staged, a separate audio boot reported `ndsp UP`,
`audio output ACTIVE`, and consumed nonzero game PCM buffers. It recorded one
initial underrun; sustained audio quality has not been qualified. Both ROM and
firmware remain ignored. OG hardware performance remains untested.
Receipts are under `experiments/local/rom-first-boot/` and
`experiments/local/audio-first-boot/`; harness captures and the active emulator
profile are under `experiments/local/azahar/`.

## Daily commands

From the repository root:

```sh
bash tools/dev.sh doctor
bash tools/dev.sh build --jobs 4
bash tools/dev.sh cia
bash tools/dev.sh extractor
bash tools/dev.sh test
```

M0 diagnostic builds and controlled GP captures have a separate workflow:
[`tools/benchmark_3ds/README.md`](../tools/benchmark_3ds/README.md). They use their
own build directory and per-run profiles; the ordinary game remains a reference.

Output paths:

- Game: `build-3ds/port/3ds/G-Diffuser-3DS.3dsx` and matching `.elf`.
- Installable package: `build-3ds/port/3ds/G-Diffuser-3DS.cia`.
- Asset-free graphics harness: `build-3ds/port/3ds/harness/gdx3ds-dl-tests.3dsx`.
- PC asset extractor: `build-extract/install/bin/gdx-extract`.

These build the existing legacy reference port. The proposed native runtime has
not been implemented. The CIA still uses upstream's title ID and shared data
directory; use the `.3dsx` and isolated emulator profile for experiments. See
[fork development](FORK-DEVELOPMENT.md) before installing on hardware.

For other development commands:

```sh
bash tools/dev.sh shell
bash tools/dev.sh run arm-none-eabi-size build-3ds/port/3ds/G-Diffuser-3DS.elf
bash tools/dev.sh run arm-none-eabi-addr2line -f -C \
  -e build-3ds/port/3ds/G-Diffuser-3DS.elf 0xADDRESS
bash tools/dev.sh run arm-none-eabi-gdb build-3ds/port/3ds/G-Diffuser-3DS.elf
```

The container requires Docker access. An agent's filesystem/network sandbox may
need escalation even though the ordinary desktop user can run Docker directly.
`tools/dev.sh build --emu` is not the host emulator launcher: the old CI smoke
still assumes macOS paths. Run the Linux host launcher below separately.

## Azahar and isolated emulator data

```sh
bash tools/azahar.sh -v
bash tools/azahar.sh build-3ds/port/3ds/harness/gdx3ds-dl-tests.3dsx
bash tools/azahar.sh build-3ds/port/3ds/G-Diffuser-3DS.3dsx
```

The launcher uses extraction mode, so FUSE is unnecessary. It sets project-local
XDG paths and does not share a personal Azahar installation's saves/configuration:

| Data | Path |
|---|---|
| Emulator config | `experiments/local/azahar/config/azahar-emu/qt-config.ini` |
| Virtual SD root | `experiments/local/azahar/data/azahar-emu/sdmc/` |
| Emulator log | `experiments/local/azahar/data/azahar-emu/log/azahar_log.txt` |
| Shader/cache data | `experiments/local/azahar/cache/` |

Azahar starts with its own default hardware settings; check the emulated model
before a test. Emulator speed does not establish OG hardware performance. Existing
graphics harness instructions and expected scenes are in
[`port/3ds/harness/README.md`](../port/3ds/harness/README.md).

## When your ROM is ready

The current extractor supports **F-Zero X USA rev0, big-endian `.z64`**. Its
expected SHA-1 is `5f658e88ffa9de23cba6986a8fd3d3a90d7b4340`; prebake validates it.
Place it in ignored `experiments/local/roms/` or keep it elsewhere on your PC.
The freshly built Linux extractor runs on this host:

```sh
python3 tools/prebake/prebake.py \
  --rom /path/to/your/fzerox-us-rev0.z64 \
  --extractor build-extract/install/bin/gdx-extract
```

This writes the validated archives into ignored `dist/sdmc/`. For the isolated
emulator, stage only those archives:

```sh
mkdir -p experiments/local/azahar/data/azahar-emu/sdmc/3ds/gdiffuser
cp dist/sdmc/3ds/gdiffuser/*.o2r \
  experiments/local/azahar/data/azahar-emu/sdmc/3ds/gdiffuser/
```

The console build itself requires no ROM. For hardware audio, the existing port
also requires your console's DSP firmware dump; follow
[`3DS-HARDWARE.md`](3DS-HARDWARE.md). We have not downloaded console system data.
For emulator audio, validate its actual firmware/HLE configuration when staging
the game; a version/help check does not establish working game audio.

## Recreate the environment

```sh
git submodule update --init --recursive --jobs 4
bash tools/dev.sh setup
bash tools/install-azahar.sh
bash tools/dev.sh build --jobs 4
bash tools/dev.sh cia
bash tools/dev.sh extractor
```

The Azahar installer pins 2126.2 and verifies SHA-256
`af037f8b775198f636b14bcfe63fb401b02246ebfefe1025bb905ce042556960` before installation.
Official sources: [devkitPro Dockerfiles](https://github.com/devkitPro/docker),
[Azahar 2126.2](https://github.com/azahar-emu/azahar/releases/tag/2126.2),
[makerom](https://github.com/3DSGuy/Project_CTR/releases/tag/makerom-v0.19.0),
[bannertool](https://github.com/carstene1ns/3ds-bannertool/releases/tag/1.2.3).
