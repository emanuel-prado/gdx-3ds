# M1a: first native machine slice

Implemented 2026-10-17 from `dev/native` baseline `9988a01`. This slice rendered
actual user-extracted USA rev0 Blue Falcon LOD2 geometry through a standalone
citro3D/PICA200 path in Azahar. It does not replace the game renderer and is not
a playable native port or an OG performance qualification.

## Delivered behavior

The offline compiler reads the established extraction's original segment-7 blob
and a strictly bounded static machine recipe. It produces a deterministic,
versioned pack with local geometry, indices, ordered material state, original
normal/UV data, bounds and content/compiler identities. Unknown recipe operations,
invalid source identity and malformed ranges fail. Runtime independently checks
size/count budgets, canonical section layout, whole-file checksum, indices,
materials and finite values before allocating GPU buffers.

The executable owns immutable linear VBO/IBO allocations, uploads local positions
and explicit RGBA attributes, and sends model/view/projection transforms to a
PICA vertex shader. Indexed draws go straight to citro3D; no Fast3D interpreter,
N64 graphics task, bridge, archive reader or game object participates. The native
link symbol audit found no legacy renderer or gameplay symbols. Shutdown drains
outstanding GPU work before releasing buffers. Rendering has no per-frame
application allocation or CPU clipping/vertex-emission path.

Materials are intentionally **unlit solid endpoint approximations** of the two
supported original recipes. Textures, decals and N64 lighting are not rendered;
this is not original visual fidelity. Eight ordered material ranges retain
original tile/primitive/environment/combiner metadata for continuation. The chosen
initial blue environment is an explicit harness parameter. The selected static
LOD2 recipe leaves game LOD semantics untouched.

Native output uses `sdmc:/3ds/gdiffuser-native/` exclusively, and builds only a
separately named `.3dsx`/ELF. No CIA/title ID, game configuration, archive, save,
simulation, physics, AI, RNG or existing fixture/protocol was changed. Existing
local setup-document edits and patched submodule trees were preserved.

Reproduction, format specification, source provenance, timing column semantics
and precise OG hardware collection steps are in
[the native workflow](../../tools/native_assets/README.md). Key commands:

```sh
python3 tools/native_assets/compile_machine.py --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r
bash tools/dev.sh native-build
bash tools/dev.sh test
python3 tools/native_assets/run_azahar.py my-m1a-run
```

Ready local binary: `build-3ds-native/gdx-native-m1a.3dsx`; matching ELF, toolchain
receipt and binary hashes are in the same directory. The private pack is
`dist/native/sdmc/3ds/gdiffuser-native/machine.gdnp`. Neither game-derived packs
nor raster captures are committed. The main reproduction requires only an
existing user-extracted archive; original extraction instructions remain intact.

## Verification receipts

| Check | Result |
| --- | --- |
| Native generation from actual extracted game data, twice | Byte identical; 8,872 bytes; 218 vertices, 288 indices, eight materials |
| Pack SHA-256 | `dde03572da88c7fe0aaae1db5128aec89c3a55637af1330cc58b6fce0b8efa98` |
| Native host tests | 13 pass; actual C loader compiled with UBSan and warnings as errors |
| Existing M0/M0.5 Python tests | All 21 pass, including the real C replay stream and 12,000-poll coverage |
| Existing portable C/C++ suites | All three pass: packing, graphics conversion and filesystem/archive/save smoke |
| Ordinary game and legacy DL harness | Both `.3dsx` builds pass through established Docker/patch gates |
| Isolated native `.3dsx` | Build passes, warnings as errors |
| Preserved M0 rendered/bypass comparison | Selected fingerprints match across all 1,000 existing samples; this rechecks saved receipts, not a newly executed race |
| Native Azahar acceptance | 720/720 frames, status 0, four captures, no fatal or unmapped-memory diagnostics |
| Near-plane diagnostic at frame 330 | 14 original triangles cross near=10; three entirely behind; eye-depth range −73.954 to 462.045 |
| Depth diagnostic | Rear instance tinted green; captures with reversed draw order are byte identical |
| Runtime corruption rejection | One-byte altered pack rejected with `ERROR pack checksum`, status 1, before rendering |
| Emulator cleanup | Host process check confirms no test emulator or AppImage wrapper remains |

The host suite additionally checks every truncation and one-byte corruption of a
synthetic pack, invalid source archives/revisions, unknown/control-flow recipes,
unloaded source vertices, out-of-bounds indices, offset/count overflows, alignment,
nonfinite/out-of-bounds coordinates, invalid colors and incomplete material ranges.
Synthetic fixtures are used only for adversarial tests; final rendering used the
actual extracted game mesh.

Private receipts: `experiments/local/native-m1a/final/` contains the manifest,
emulator log, report and isolated SD's `run.log`, `frames.csv`, `scene0..3.bmp`.
`corrupt-rejected/` is an intentionally failed run confirming rejection.
`ordinary-build.log`, `host-tests-final.log` and `m0-preserved-comparison.json`
record other checks. No captured game content is published with this report.
Source identity in the accepted binary is
`7d15efbf9ad77891b22391aab603e0fb00f2296a9bba1b84e83f230d4b49dc23`;
this hashes main/loader/shader/header, independently of unrelated preserved local
changes that make the checkout's Git build label dirty.

## Measurements and limits

Environment: host Linux x86_64, Azahar 2126.2, explicitly selected OG model, mono
400x240, normal-speed request. Toolchain: devkitARM r68-1 / GCC 16.1.0,
libctru 2.7.0-1, citro3d 1.7.1-2, 3dstools 1.3.1-3 in `gdx-3ds-dev:local`,
using the project's pinned devkitPro base. Versions are embedded in the guest log.

| Metric | Azahar observation |
| --- | ---: |
| CPU work median / p95 | 0.452 / 0.525 ms |
| Previous GPU queue median / p95 | 0.249 / 0.249 ms |
| Immutable VBO / IBO | 7,848 / 576 bytes |
| Transient pack read buffer, freed before frames | 8,872 bytes |
| Command buffer requested | 262,144 bytes |
| Allocator linear delta during renderer setup | 270,720 bytes |
| Render target color + depth/stencil | 768,000 bytes |
| Free linear bytes after setup | 31,670,912 bytes |
| Free VRAM after setup | 5,523,456 bytes |
| Ordinary live heap after setup | 19,648 bytes |
| ELF text / data / BSS | 157,376 / 7,608 / 19,264 bytes |

Timing summary excludes the first 30 frames and the first six frames of each
phase; raw CSV retains every frame. GPU timing is read after waiting for prior
GPU completion and includes display transfer. CPU excludes FrameBegin waits,
SD/console/capture work and the one-off clipping diagnostic. Sparse emulated tick
values are not hardware timing precision. Instrumentation can stall presentation;
no sustained 60 Hz or deadline claim follows from these intervals.

Allocator snapshots and explicit owner sizes are not total process commit or
measured peak application memory. Image, reserved free heaps, platform allocations
and earlier framebuffer allocations need separate accounting on hardware. There
is no claim of a steady racing workload, integrated 30-machine cost, original
materials or OG feasibility. The M1 CPU ≤5 ms / GPU ≤12 ms screening gates remain
**unmeasured on physical original 3DS**.

Physical hardware was unavailable. Follow the workflow's untouched 720-frame run,
three repetitions, separate lid/early-exit checks and log/binary/toolchain collection
before assessing real hardware behavior. Visible clipping and winding still need
hardware inspection; emulator screenshots alone cannot qualify PICA precision or
complete original fidelity.

The user-provided `manual-race` recording remains unfinalized and unmodified.
It was not repaired, completed or relabeled for this renderer task. M0.5's manual
full-race acceptance remains separate and open.

## Suggested M1b continuation

1. Extend this proven machine recipe with extracted textures and a finite native
   material catalog. Validate signed normals, lighting, UV scales, tile/mirror
   semantics and livery endpoints against the reference machine on OG hardware.
2. Add complete machine LOD coverage and a bounded 30-instance scene after a
   source/material census. Preserve the original-rule gameplay LOD independently;
   do not integrate simulation or alter the replay oracle to simplify rendering.
3. Add a camera-relative track chunk/precision slice with shared-origin changes,
   tunnel/near-plane cases and explicit residency. The present local-mesh scene
   does not prove large-coordinate track precision or streaming.
4. Measure actual OG CPU/GPU/memory and traced versus untraced presentation before
   integrating any native scene adapter into the legacy game loop.
