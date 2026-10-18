# M1b immutable texture upload diagnostic

This executable proves a bounded native upload boundary for the eight Blue
Falcon textures. It does not implement machine materials, original sampler
semantics, filtering, lighting, FLX alpha, or livery rendering. The M1a executable,
mesh format and shader remain available unchanged.

## Build and run

```sh
python3 tools/native_assets/compile_textures.py --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r
python3 tools/native_assets/compile_upload.py \
  --bundle dist/native/sdmc/3ds/gdiffuser-native/blue-falcon-textures.gdnt
python3 -m unittest discover -s tools/native_assets -p 'test_native*.py' -v
bash tools/dev.sh native-build
python3 tools/native_assets/run_swatch.py my-upload-run
# Optional manual launch, after staging a separate isolated profile:
timeout --signal=TERM --kill-after=5s 45s \
  bash tools/azahar.sh build-3ds-native/gdx-native-swatch.3dsx
```

Use an isolated Azahar profile and mount/copy
`dist/native/sdmc/3ds/gdiffuser-native-swatch/textures.gdns` to its SD directory.
The `run_swatch.py` command stages a fresh isolated OG-model profile, requires
completion, compares all 4,612 source-derived RGB/marker samples and verifies
process-group cleanup. It writes hashes, logs and a JSON report under ignored
`experiments/local/native-swatch/<label>/`. Use a new label for every run.
`--expect-rejection --pack <corrupted-copy>` instead requires pack validation
failure before any GPU upload. The optional timeout command is a bounded manual
launch, not an automated acceptance test;
close only the launched process group as soon as the test completes and verify
the wrapper/emulator have exited. Original-3DS users launch the distinct
`gdx-native-swatch.3dsx` from HBL with the same native-swatch SD directory.
No CIA/title ID is introduced; no legacy assets or saves are opened.

Outputs under `sdmc:/3ds/gdiffuser-native-swatch/` are `run.log` and
`swatches.bmp`; previous diagnostic outputs are overwritten. Automatic exit is
after 120 presented frames; START or lifecycle interruption produces status 2
and cannot pass. Required successful log fields are `capture_swatches=1`,
`completed_frames=120 expected=120`, `exit_status=0`, and `SWATCH_COMPLETE`.
The log identifies toolchain, C source/shader hash, build revision, console model,
normal-speed request, validated pack CRC and allocation sizes. A linked worktree
inside Docker may lack common Git metadata: configure with
`-DNATIVE_BUILD_ID_OVERRIDE=<exact-commit>` when available; otherwise the explicit
`unavailable-isolated-worktree` label appears, never an invented commit.
`build-3ds-native/SHA256SUMS` and `toolchain.txt` identify both binaries/ELFs.

## Fixed wire format and allocation boundary

The device reads only `.gdns`, never JSON, ZIP, N64 commands or a ROM. The host
converter validates the existing bounded `.gdnt` bundle before creating `.gdns`.
All integers are little-endian u32. The file size is exactly 18,944 bytes:

| Offset | Field |
| --- | --- |
| 0 | Eight-byte magic `GDXSWCH\0` |
| 8 | Version=1 |
| 12 | Total size=18944 |
| 16 | Texture count=8 |
| 20 | Entry offset=128 |
| 24 | Pixel payload offset=512 |
| 28 | CRC32 of entire file with this field zero |
| 32 | Source setup segment SHA-256, 32 bytes |
| 64 | Source texture-loader recipe SHA-256, 32 bytes |
| 96 | 32 reserved zero bytes |
| 128 | Eight 48-byte tile records |
| 512 | Contiguous GPU_RGBA8 pixel data, 18,432 bytes |

Each record contains tile ID, width, height, original format (I4=1, IA4=2,
RGBA16=3), absolute pixel offset, byte count, S/T modes (wrap=0,
mirror+clamp=1), S/T masks, S/T shifts. Catalog and identities are exactly those
documented in [m1b-textures.md](m1b-textures.md). The C validator checks every
field, canonical offsets, exact total length, all pixel ranges, reserved bytes,
identities and full-file CRC; errors zero the output. It performs no allocation
and uses explicit byte loads, including for unaligned input. CRC/provenance
metadata detect corruption and identify the supported source; they do not
authenticate hostile replacement of assets.

The executable bounds file length before allocating one 18,944-byte read buffer.
It validates before any citro3D/GPU allocation. Each of eight immutable original
textures is uploaded once, followed by one synthetic 8×8 orientation marker.
The read buffer is released after upload; a single 1,080-byte immutable VBO holds
all nine quads. No application allocation, pixel conversion, vertex generation
or CPU vertex transformation occurs during frames. Shutdown drains GPU work
before freeing textures and vertices; partial setup failures release each
successfully initialized owner. The render target costs 768,000 bytes and the
command buffer 65,536 bytes. Allocation counters are diagnostic, not total
process-memory or measured transition peaks.

## Pixel acceptance

The scene uses nearest filtering and clamp-to-edge on every swatch, deliberately
independent of preserved original sampler metadata. Blending uses ONE/ZERO and
alpha testing is disabled: even IA4 pixels with alpha zero display their stored
RGB. Original material transparency is outside this diagnostic.

BMP coordinates below use the top-left origin, width 400, height 240:

| Content | x | y | width | height |
| --- | --- | --- | --- | --- |
| Tiles 0,1,2,3 | 8,106,204,302 | 8 | 64 | 64 |
| Tile 4 | 8 | 92 | 80 | 20 |
| Tile 5 | 106 | 92 | 32 | 64 |
| Tiles 6,7 | 204,302 | 92 | 64 | 64 |
| Orientation marker | 16 | 192 | 32 | 32 |

The marker must show red at top left, green at top right, blue at bottom left,
white at bottom right. Check interior pixels against the independently decoded
host RGBA values, accounting for nearest-neighbor sampling at pixel centers.
Colors alone or a nonempty image do not pass orientation/channel verification.
The original textures use bottom-up Morton8/ABGR storage. Screen top-left UV is
`(0,0)`, bottom-right is `(1,1)`: the bounded emulator pixel comparison verified
this direction for the tilted orthographic projection and framebuffer transform.

## Validation evidence

- 30 combined native host tests pass. Five new tests exercise the fixed C
  validator with UBSan and fatal sanitizer errors: valid synthetic input,
  deterministic conversion, corruption across header/records/payload, repaired
  CRC attacks on every record field, truncated/excess input, null and unaligned
  pointers, plus rejected invalid host bundles.
- Real owned-source conversion: 18,944-byte pack SHA-256
  `77fcc6b74ec5acea50e02dd8ec16ca85255958e4b9abd4878db8d52587b89174`.
- Both standalone executables build with devkitARM and `-Wall -Wextra -Werror`.
- Independent bounded Azahar OG-profile run `upload-orientation-a` completed
  120 frames. All 4,612 host-decoded RGB and synthetic corner pixel checks
  matched exactly; there were no pixel failures. Emulator process-group and
  host-wrapper cleanup passed. Machine-readable local evidence is
  `experiments/local/native-swatch/upload-orientation-a/report.json` in the
  integration checkout. This establishes GPU orientation, channel layout and
  swatch upload in Azahar; physical original-3DS upload, memory and lifecycle
  acceptance remain pending. This static scene is not a machine-fidelity or
  performance benchmark.
- The reusable runner repeats this result on the integration build in
  `upload-final-a`: 4,612 exact RGB samples and cleanup pass. In
  `corrupt-rejected-a`, a one-byte payload mutation is rejected with validation
  error/status 1 before GPU upload. Both host process inspections confirm the
  emulator and wrapper exited. These receipts remain under the same ignored
  `experiments/local/native-swatch/` directory.
