# M1b host texture slice

Status: host compiler validated; native texture rendering, material fidelity and
hardware acceptance remain pending. The M1a v1 mesh pack and native executable
are unchanged. This bundle is an experimental input to the next native slice,
not a claim that M1b is complete.

## Reproduce

```sh
python3 -m unittest discover -s tools/native_assets -p 'test_native*.py' -v
python3 tools/native_assets/compile_textures.py \
  --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r
```

`--source /path/to/pinned/decomp/src/overlays/ovl_i9/machine_draw.c` supports
isolated worktrees. The recipe body must match its pinned hash. `--out` selects
the output; default is the ignored native data directory, separate from legacy
assets/saves. Python's standard library is sufficient. Tests use synthetic
source data and need no ROM, extracted assets or decomp checkout. Source identity
constants are mocked only inside synthetic tests; production compilation always
checks the complete original source segment and recipe.

## Finite source catalog

Offsets are relative to segment 3, the **entire** `segment_blob/setup_gfx` resource;
do not subtract the machine-custom carve offset `0x780`. Source metadata is in
`decomp/assets/yaml/us/rev0/machine_custom_gfx.yaml:202` and
`decomp/assets/yaml/us/rev0/segment_blob.yaml:42`. The texture loader is
`decomp/src/overlays/ovl_i9/machine_draw.c:16118`.

| Tile | Original symbol | Offset | Format | Size | S / T mode | S / T mask bits |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | D_3004618 | 0x4618 | I4 | 16×16 | mirror+clamp / mirror+clamp | 4 / 4 |
| 1 | aDecalBlueFalconWingCheckeredTex | 0x4918 | RGBA16 | 16×16 | mirror+clamp / wrap | 4 / 4 |
| 2 | aDecalStripeTex | 0x4698 | IA4 | 16×16 | mirror+clamp / wrap | 4 / 4 |
| 3 | aDecalBlueFalconArrowTex | 0x4598 | I4 | 16×16 | mirror+clamp / mirror+clamp | 4 / 4 |
| 4 | aLogoBlueFalconTex | 0x4718 | I4 | 64×16 | mirror+clamp / mirror+clamp | 6 / 4 |
| 5 | aMachineNumber7Tex | 0x4498 | I4 | 16×32 | mirror+clamp / mirror+clamp | 4 / 5 |
| 6 | aRearDuctTex | 0x4D18 | I4 | 32×32 | mirror+clamp / mirror+clamp | 5 / 5 |
| 7 | aBooster1Tex | 0x4B18 | I4 | 32×32 | mirror+clamp / wrap | 5 / 5 |

Tile 0 is supplied by setup display list `D_303A6A8`, not the Blue Falcon
texture-loader function. Its checked source commands at offsets `0x3A718` through
`0x3A748` load `0x03004618`, set tile 0 to I4, mask 4/4, mirror+clamp in both
directions, and a 16×16 tile rectangle. The alternate end-cutscene setup
`D_303A5F8` loads the same texture. All eight catalog entries have zero tile
shifts, zero tile origins and no palette. Modes are preserved as N64 metadata;
this slice does not claim PICA sampler equivalence for combined mirror+clamp.

The source resource must be 250,736 bytes with SHA-256
`f654cebe506385d9bb3ce8664cbf6dcd96593c6600f3e8486c31a019b3a96934`.
ZIP CRC, unique resource name, bounded resource size, Torch BLOB type/size,
full-source hash and exact loader-body hash are checked before conversion.
Unsupported revisions, formats, sizes and recipes fail explicitly.

## Conversion and output contract

I4 expands the high nibble first, with intensity copied into **alpha as well as
RGB**. IA4 has three intensity bits and one alpha bit; RDP bit replication yields
the intensity table `0,36,73,109,146,182,219,255`, with binary alpha. RGBA16 is
big-endian RGBA5551, expanding each five-bit component by `(n<<3)|(n>>2)`.
The primary implementation reference is paraLLEl-RDP's
[convert_rgba16 and sample_texel_ia4](https://github.com/Themaister/parallel-rdp/blob/master/parallel-rdp/shaders/texture.h#L70-L118)
(inspected 2026-10-17). Full-range and intermediate-value vectors cover both
rules. The retained legacy importer uses `n*36` for IA4 (maximum 252) and
`n*255//31` for RGBA16; those approximations are deliberately not carried into
the native compiler. Future comparison captures must account for this known
legacy reference difference.

GPU payloads contain 8×8 Morton tiles, tiled rows from bottom to top, with each
GPU_RGBA8 texel stored as little-endian `R<<24|G<<16|B<<8|A` (bytes A,B,G,R).
This matches `port/3ds/gfx/gfx_citro3d.cpp:2011`, including its verified vertical
orientation. All catalog dimensions are powers of two, so there is no padding.
Known-coordinate tests cover row reversal, byte order and both tile axes.
Actual orientation under the future native UV shader still requires rendering.

The independent `.gdnt` bundle has a 48-byte header: magic `GDXM1BT\0`,
little-endian u32 version=1, u32 JSON length, and 32-byte SHA-256 of the remaining
content. Canonical ASCII JSON metadata precedes concatenated GPU payloads.
Texture offsets are relative to the payload start. Metadata identifies the source,
recipe, layout, source slices, tile semantics and per-texture hashes. The host
validator enforces the exact catalog, contiguous ranges, dimensions, hashes,
canonical metadata and total budget (128 KiB). Checksums detect corruption, not
malicious replacement. A future native loader must independently validate its
eventual schema before allocation; no native loader accepts this bundle today.
Output uses a unique temporary sibling and atomic rename.

## Actual validation

- 25 native asset/texture tests passed, including the existing M1a C loader
  tests with UBSan. Twelve new tests cover source rejection, ZIP CRC/duplicates,
  decoder vectors, alpha, Morton layout, deterministic output, corrupted bundles
  and recalculated-checksum catalog/range mutations.
- Real owned-archive compilation produced 8 tiles, 18,432 GPU payload bytes,
  21,865 bundle bytes, SHA-256
  `37f8e03e3f5214e3f0edb4e6076bd5d4c0cede28520f4ae2a9d992e31cfa16b3`.
- Real source comparison against `gen_dump_all.py`: seven tiles decode
  identically. Tile 2 (IA4 stripe) differs in 480 RGB channel bytes, with maximum
  difference 3/255, due to the documented bit-replication correction. Alpha is
  unchanged. This particular RGBA16 tile uses values where both expansions
  coincide; intermediate-value tests cover their difference. No proprietary
  bytes are committed. No emulator or hardware result is claimed for this slice.

## Exact next rendering slice and remaining audit

Add a separately versioned validated native texture/material input, upload the
eight immutable textures once, and implement the two finite LOD2 combiner recipes
from `machine_draw.c:5100`: `(texel-env)*texel_alpha+env` and
`(primitive-env)*texel+env`, followed by multiplication by SHADE. Both recipes use
environment alpha in cycle 1 and carry COMBINED alpha through cycle 2. Preserve
eight ordered mesh ranges, signed UVs and per-range primitive/environment colors.
The caller sets initial environment from `racer->bodyR/G/B` (`racer.c:6127`);
M1a's hardcoded initial blue remains a harness choice. Runtime livery variants,
filtering, clamp/mirror edge behavior, alpha, blending and depth need equivalent
camera captures against the reference before visual fidelity can pass.

Do **not** infer ordinary environment-map UV generation solely from
`G_TEXTURE_GEN`. The race setup mode includes that bit, but the F-Zero FLX
microcode path uses it for LUT-derived vertex alpha while retaining signed source
UVs (`libultraship/src/fast/interpreter.cpp:3697`). `racer.c:6110` loads its DMEM
LUT and look-at light. The generic generated-UV path is the alternate branch;
the end-cutscene setup differs. Signed normals, directional+ambient lighting,
FLX alpha, tunnel-dependent light and fog remain a separate required audit.
