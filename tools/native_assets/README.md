# Native M1a machine pack

This compiler extends PC prebake with an independent native output. It reads the
user-extracted `fzerox.o2r` and compiles **Blue Falcon LOD2**, not a captured frame
or a replacement mesh. The native executable never opens that archive.

```sh
# Existing extraction, only if you have not already prebaked your own ROM:
python3 tools/prebake/prebake.py --rom /path/to/fzerox-us-rev0.z64 \
  --extractor build-extract/install/bin/gdx-extract
# Native compilation (Python standard library only):
python3 tools/native_assets/compile_machine.py \
  --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r
bash tools/dev.sh native-build
bash tools/dev.sh test
python3 tools/native_assets/run_azahar.py my-m1a-run
```

The pack lands in `dist/native/sdmc/3ds/gdiffuser-native/machine.gdnp`. The isolated
executable and ELF are `build-3ds-native/gdx-native-m1a.{3dsx,elf}`. Copy the pack
to `sdmc:/3ds/gdiffuser-native/machine.gdnp` and the `.3dsx` to the Homebrew Launcher.
No CIA is generated and no title ID is reused. No game archives, firmware, saves,
configuration, audio or replay input are needed on the device. Existing archives
are read only during PC compilation; all native generated output is separate.

The standalone build is also reproducible with:

```sh
bash tools/dev.sh run cmake -S port/3ds/native -B build-3ds-native \
  -DCMAKE_TOOLCHAIN_FILE=/opt/devkitpro/cmake/3DS.cmake -DCMAKE_BUILD_TYPE=Release
bash tools/dev.sh run cmake --build build-3ds-native --parallel 4
```

## Source and conversion boundary

`segment_blob/machine_global_gfx` contains the original big-endian segment 7.
The compiler verifies its Torch BLOB size/type, ZIP CRC and USA rev0 SHA-256
`f19a962ab79e3edb5e31266a5f1137710ae31eaebf2d871b865652064c638194`.
This same segment is a byte-exact ROM slice at `0x1e23f0`, length `0x48cb0`;
see `decomp/assets/yaml/us/rev0/segment_blob.yaml`. Existing prebake validates the
whole source ROM. This tool independently verifies the actual segment consumed,
including when archive compression has been changed by the established store step.

The offline recipe is `Machine_DrawBlueFalconLod2` in the pinned
`decomp/src/overlays/ovl_i9/machine_draw.c`. It has static triangle/vertex calls
and no gameplay side effects or dynamic control flow. The compiler accepts only
its explicit vertex, triangle, pipe-sync, primitive/environment color, texture-tile
and two combiner recipes. Unknown operations, combiners or control flow fail.
It does not execute game C or interpret runtime display lists. The existing LOD1
function's hardware waits and game-state writes are deliberately outside this
recipe. Selecting a standalone LOD2 mesh changes no gameplay LOD selection.

Positions keep signed N64 units/axes without normalization. Triangle order is
unchanged, and vertices deduplicate only within equivalent source/material state.
The signed UV values and original normal/alpha bytes survive in the native vertex.
The first environment color is an explicitly chosen blue `(14,99,165,255)`;
primitive starts white. Recipe color changes, tile IDs and combiner selectors
are preserved in eight ordered material ranges.

**M1a material limitation:** no textures or N64 lighting are evaluated. Color is
the environment endpoint for the first combiner and the primitive endpoint for
the second. This displays blue, white, yellow and pale-blue surfaces but cannot
reproduce the decals, number, ducts, lighting or original livery. Original signed
normal bytes are never misinterpreted as unsigned vertex colors. The GPU consumes
explicit normalized RGBA colors. Pack flag `1` requires this approximation;
unknown flags/material recipes are rejected. Texture state/UVs remain inputs for
M1b, not a claim of original material fidelity.

## Version 1 wire format

All numeric fields are little-endian; IEEE float32 is used. No pointers, paths,
timestamps, platform-dependent padding or runtime GBI commands are serialized.
Version 1 denotes this single Blue Falcon LOD2 asset; broader content needs a
new schema. Counts, offsets, identity, bounds and material semantics are metadata.

| Offset | Content |
| --- | --- |
| 0 | Eight-byte magic `GDXM1A\0\0` |
| 8 | Ten u32: version, total size, vertex/index/material counts, vertex/index/material offsets, CRC32, flags |
| 48 | Source ROM SHA-1 (20 bytes) |
| 68 | Source segment SHA-256 (32 bytes) |
| 100 | Exact function-body SHA-256 (32 bytes) |
| 132 | Compiler script SHA-256 (32 bytes) |
| 164 | AABB min xyz / max xyz (six float32) |
| 188 | Reserved u32, zero |
| 192 | Vertex array: float32 xyz + float32 RGBA + four original normal/alpha bytes + signed i16 UV; 36 bytes each |
| after vertices | u16 indices; zero padding to four-byte alignment |
| after indices | Materials: u32 first index, index count, tile, packed RGBA primitive, packed RGBA environment, combiner, flags=1, reserved=0; 32 bytes each |

CRC32 covers the **entire file** with bytes 40..43 set to zero. It detects damage;
it is not authentication. Identity hashes establish provenance/reproducibility,
not a signature. Canonical offsets prohibit overlapping, missing or trailing
sections. The loader checks file/decoded budgets, alignment, all indices,
material coverage, flags, finite positions/colors/bounds and vertex containment
before exposing borrowed views. Caps are 1 MiB file, 4,096 vertices, 24,576 indices,
64 materials. This slice needs only 8,872 file bytes, 218 vertices, 288 indices
and eight materials. Generation uses a temporary file plus atomic rename.

The C loader allocates nothing. Runtime owns one bounded read buffer, then one
immutable linear VBO/IBO pair and a bounded material array. It releases the read
buffer after upload, flushes GPU-visible writes before drawing and drains the
GPU queue through `C3D_Fini` before freeing the VBO/IBO. No per-frame application
allocation, vertex transformation or clipping feeds frame rendering. One
post-timing diagnostic independently transforms the real vertices to count
near-plane crossings; it never generates rendered geometry.

## Test scene and hardware collection

The app runs 720 presented frames, then exits. START exits early (status 2).
A toggles automatic rotation; D-pad left/right adjusts the angle. Leave controls
untouched for reproducible captures. The phases are:

1. Frames 0–239: rotate the actual mesh with backface culling enabled.
2. Frames 240–479: move through the mesh, near=10, far=4000. At frame 330,
   record how many original triangles cross the near plane. GPU clipping handles
   vertices behind the near plane and camera; no CPU clipping path is used.
3. Frames 480–719: two overlapping instances with a green tint on the rear one.
   Reverse submission order every 60 frames with the same camera/model matrices.
   `scene2.bmp` and `scene3.bmp` must be byte identical: depth, rather than order,
   determines occlusion. Projection uses PICA's reversed depth and clear=0.

Inspect `scene0.bmp` through `scene3.bmp` for recognizable silhouette, orientation,
clipping and backface behavior. These are raster smoke checks, not a comparison
against full original livery. The top output is mono 400x240. The harness requests
normal CPU speed; the run log identifies the model and request. Azahar is launched
with an isolated OG-model profile. Its timing remains emulator timing.

Every run overwrites only the native directory's `run.log`, `frames.csv` and four
BMPs. Copy them before the next run. The Azahar runner creates a fresh labeled
profile under ignored `experiments/local/native-m1a/`, records binary/pack hashes,
checks completion, nonempty rendering, crossing triangles and depth equality,
and terminates its test process group. A separate GNU timeout bounds descendants
even if the runner is interrupted. Host process inspection distinguishes exited
zombies from live emulator/wrapper processes.

For **physical OG hardware**, use the `.3dsx` through the Homebrew Launcher, normal
clock, mono; leave input untouched until automatic exit. Collect the six native
outputs, the matching `.3dsx`/ELF, `build-3ds-native/{SHA256SUMS,toolchain.txt}`,
console model/system/HBL versions and any visible errors. Repeat three times;
test close/reopen of the lid and START exit separately. The latter are manual
lifecycle checks, not part of the 720-frame deterministic capture.

`frames.csv` reports explicitly timed CPU submission work (after FrameBegin's
waits, through FrameEnd), citro3D processing time, **previous** completed GPU queue
time, free linear bytes, ordinary live heap and command-buffer fraction. GPU queue
time includes display transfers. CSV writes, console output, BMP writes and the
clipping diagnostic are outside the CPU interval; their stalls can affect pacing.
This diagnostic does not establish sustained presentation deadlines. Do not add
CPU/GPU values, infer OG costs from Azahar, or compare this one-machine unlit
scene with the complete M1 hardware screening gates (CPU ≤5 ms, GPU ≤12 ms).

`run.log` records source/build/compiler/toolchain identities, source ROM/segment/
recipe/compiler hashes, pack CRC, VBO/IBO/read-buffer/command sizes, render-target
bytes, allocator counters and completion. `heap_live` excludes image, free reserved
heaps, linear and VRAM; `linear_delta` excludes allocations before renderer setup.
The render target is 768,000 bytes (RGBA8 + depth24/stencil8). These are owner and
allocator snapshots, not total process commit or a measured startup peak.
