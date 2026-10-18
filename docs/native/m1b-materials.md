# Textured Blue Falcon diagnostic

Status: bounded unlit material slice; full M1b fidelity and physical hardware
acceptance remain open. This executable draws the real LOD2 geometry with all
eight original textures and two finite material recipes. It links no game,
Fast3D/display-list interpreter, scheduler or audio engine.

```sh
python3 tools/native_assets/compile_machine.py --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r
python3 tools/native_assets/compile_textures.py --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r
python3 tools/native_assets/compile_upload.py --bundle dist/native/sdmc/3ds/gdiffuser-native/blue-falcon-textures.gdnt
bash tools/dev.sh native-build
python3 tools/native_assets/run_materials.py my-material-run
```

The executable `build-3ds-native/gdx-native-materials.3dsx` reads only
`sdmc:/3ds/gdiffuser-native-materials/{machine.gdnp,textures.gdns}` and writes
`run.log`, `frames.csv`, `scene0..3.bmp` there. The runner creates a fresh isolated
OG-profile SD and stages both packs, preserving every existing save and harness.
No CIA or title ID is introduced. Build/ELF hashes and toolchain receipts remain
in `build-3ds-native/`. Binary and pack hashes accompany local run reports.

## Explicit scene, finite materials

The v1 M1a pack retains its original approximation flag/vertex colors. This new
scene (`blue-falcon-textured-unlit-v1`) ignores those color attributes and uses
only validated geometry, signed UVs and source material records. A separate
preparation boundary requires all eight exact ordered recipe/range/flag records;
unknown records fail explicitly, before GPU setup. The stock initial environment
RGB `(0,0,255)` overrides the first five ranges; subsequent black and blue-gray
recipe colors remain intact. No borrowed input is modified.

The two finite RGB equations are `(T-E)*T.a+E` and `(P-E)*T.rgb+E`.
The second uses PICA stages `E*(1-T)` then `T*P+previous`, avoiding an intermediate
negative subtract/clamp. Alpha retains environment alpha. The scene explicitly
sets **shade RGB=1 and FLX alpha=0**; these values describe a diagnostic, not
unsupported-state fallback. Runtime never reads N64 commands. Mesh/texture packs
are checked independently before GPU allocation, uploaded once, then released;
immutable vertex/index/texture owners survive outstanding GPU work and cleanup.

The vertex shader preserves signed coordinates with
`floor(rawUV * 65535/65536)/(32*textureDimension)`. It transforms geometry on PICA,
with per-draw texture dimensions. Normal/color fields survive the pack but are
not evaluated as lighting. Samplers deliberately use nearest filtering, clamp S,
and repeat T only on tiles 1,2,7. Original mirror+clamp edge behavior and N64
three-point filtering are **not qualified** by this scene.

[The source material audit](m1b-material-audit.md) identifies the required next
lighting, FLX vertex lookup/blender, original sampler and matching-camera checks.
No original-quality equivalence or OG performance claim follows from this slice.

## Executable gate and evidence

360 presented frames: orbit 0–119, near-plane traversal 120–239, fixed material
grid 240–359. Captures at 60/165 show the real textured machine and clipping;
260/320 capture the same grid and must be byte identical. The grid uses the same
signed-UV shader and material state as the mesh. Eight 80×64 rectangles start
at `(8+(slot%4)*98,8+(slot/4)*84)`, source tiles in recipe order
`1,2,3,4,5,6,7,0`. The runner independently decodes the owned source and evaluates
the equations at 4,608 texel sample positions. The explicit RGB error gate is
one level, accounting for two-stage PICA quantization; it is not a waiver for
lighting/filter/material mismatches in future fidelity acceptance.

- Initial run exposed a real grid-buffer binding defect despite a recognizable
  3D machine: the descriptor was modified without marking citro3D state dirty.
  Reacquiring `C3D_GetBufInfo()` at the grid boundary fixes GPU submission.
  The same unchanged pixel oracle then passes. Failed receipt is preserved at
  ignored `experiments/local/native-materials/first-material-grid/`.
- Corrected run `material-grid-binding-fixed` completes 360 frames, exercises
  near-plane crossings and produces stable grid captures. Of 4,608 samples,
  4,512 match exactly and 96 differ by one RGB level; maximum error 1. Test group
  and host AppImage/emulator processes exited.
- All 33 native host tests pass, including three new tests of the actual C
  material preparation boundary under UBSan (every record field mutation,
  source preservation, stock colors, rejected counts/nulls).
- Independent review inspected scene validation, shader equations, buffer cache
  and lifetime, dirty-state correction and explicit fidelity limits: no blocker.
- Existing M1a and swatch executables/formats/shaders remain available. New
  buffers add 1,728 bytes for diagnostic quads; original texture payload is
  18,432 bytes. Allocator snapshots and submission CSV are diagnostic and do
  not measure total process memory or sustained presentation deadlines.

- Integration-build run `material-final-b` passes the reusable oracle with the
  same 4,512 exact / 96 one-level results, 360 ordered frames, stable grid and
  14 near-plane crossing triangles. `unsupported-material-rejected` changes a
  source recipe endpoint and repairs its CRC: the executable rejects the unknown
  material scene before upload. Both test emulator/wrapper instances exited.
  Receipts are under ignored `experiments/local/native-materials/`.

Physical original-3DS appearance, timing, memory and lifecycle remain untested.
