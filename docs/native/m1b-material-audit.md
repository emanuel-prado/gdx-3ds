# Blue Falcon material implementation boundary

Source audit, 2026-10-17; no material GPU fidelity claimed. This is the concrete
continuation after texture decoding/upload, not a completed M1b gate.

The two LOD2 combiner recipes in `machine_draw.c:5100` produce:

- `C = ((T.rgb - E.rgb) * T.a + E.rgb) * S.rgb`
- `C = ((P.rgb - E.rgb) * T.rgb + E.rgb) * S.rgb`

T is the selected texture, E environment color, P primitive color, S lit shade.
Both recipes retain environment alpha (one for this model). Preserve eight
ordered material ranges. Clamp/rounding at N64 cycle boundaries and PICA stage
rounding still require explicit reference vectors and GPU comparison.

Initial E is `racer->bodyR/G/B` (`racer.c:6128`), with default Captain Falcon skin
RGB `(0,0,255)` (`racer.c:468,1584`). The recipe later switches E to black and
then `(14,99,165)` (`machine_draw.c:5165,5180`). M1a's chosen initial blue is an
explicit approximation, not the stock skin to carry into accurate materials.

## Lighting and FLX blender

Normals are signed bytes and retain their original magnitude; do not normalize
each source normal. Directional light is transformed by the transposed current
model matrix and normalized. Positive dot contribution is divided by 127 and
added to ambient, then capped at 255 in the retained reference
(`interpreter.cpp:3316,3625–3695`). Original outdoor ambient is 100, directional
RGB 255, direction `(69,69,69)` (`racer.c:1838`). Indoor ambient varies 50–100;
the course segment up vector affects direction (`racer.c:6040–6098`).

The race setup `D_303A6A8` has geometry mode `0x00a60405`, lighting plus
`G_TEXTURE_GEN`, without `G_FOG`. Its `othermode_l=0xc8000230` selects
`G_RM_FOG_SHADE_A` (`gbi.h:1016`):

`output.rgb = F.rgb * q + C.rgb * (1 - q)`

F is the racer's fog/highlight color and q is **interpolated vertex shade alpha**.
This is not ordinary geometric distance fog. The FLX path retains signed stored
UVs and instead uses the texture-generation bit for lookup-derived vertex alpha
(`interpreter.cpp:3698–3711,3834–3835`). `racer.c:6105–6110` sets alpha-light
s16 components from rounded `(sun - camera.basis.x) * 16383` and loads the
256-byte `D_800CE3D0` LUT (`racer.c:333`). The retained interpreter reads the
light divided by 256, normalizes, transforms by transposed model matrix,
normalizes, truncates its dot with signed source normal, clamps to [-128,127],
then uses `LUT[128+index]/255`. Audit original microcode equivalence before
counting this retained implementation as definitive arithmetic proof.

Compute q at vertices before interpolation: looking up the interpolated dot in a
fragment stage changes nonlinear lookup results. The end-cutscene setup differs
and needs its own state variant.

A finite PICA mapping to test is texture interpolation for recipe 0; for recipe 1,
`(1-T)*E` followed by `T*P + previous` (MULTIPLY_ADD), then shade multiplication.
One final INTERPOLATE stage implements F/q blending. Three or four stages suffice
algebraically, with one constant per stage. This proposal remains unvalidated
for saturation/rounding, alpha and PICA operand behavior.

## Signed UV and sampler audit

All tiles have zero shift/origin. All S axes use mirror+clamp. T wraps for tiles
1,2,7; other T axes use mirror+clamp. Preserve the exact catalog from
[m1b-textures.md](m1b-textures.md); mirror+clamp is not mirror-repeat.

The retained path quantizes signed 10.5 UV by arithmetic
`floor(raw * 65535 / 65536)`, then divides by 32, applies shifts/origin and adds
a half texel for bilerp (`interpreter.cpp:3620,5219–5251`). Replacing 0xFFFF with
exactly one changes positive coordinates. Real per-material raw ranges are:

| Tile | U min/max | V min/max |
| --- | --- | --- |
| 0 | -287 / 799 | 0 / 512 |
| 1 | -466 / 597 | -614 / 2048 |
| 2 | -110 / 1738 | -82 / 618 |
| 3 | -539 / 512 | 30 / 512 |
| 4 | -2200 / 4211 | -774 / 1189 |
| 5 | -1071 / 1583 | -1869 / 1195 |
| 6 | -372 / 1303 | -69 / 1023 |
| 7 | -1229 / 2253 | -1039 / 1051 |

The next useful machine slice consumes the validated textures, implements these
two finite recipes plus original shade/FLX inputs, rejects unknown states and
compares identical cameras. Upload swatches alone cannot qualify these semantics.
