# M0: first controlled GP measurement slice

Date: 2026-10-14. Status: diagnostic infrastructure and emulator checks complete;
OG hardware feasibility, full-race equivalence, detailed audio cost and complete
content/material inventory remain open. No native renderer is implemented yet.

## Implemented

- An opt-in `GDX3DS_BENCHMARK` target configuration in a separate build directory.
- Link-time wrappers for game update, original draw generation, graphics tasks,
  presentation fallback and explicit benchmark race initialization.
- Fixed-storage per-game-tick captures, written after the measurement stops.
- A menu-driven Jack Cup first-course start with 30 racers, fixed seeds/frame
  phase and straight acceleration. Menus are excluded from the 1,000-tick capture.
- Identical explicit vblank pacing in rendered and graphics-task-bypass modes.
- A fresh emulator profile and saves per run, input/binary hashes, capture
  completeness/coverage guards and tick-by-tick semantic fingerprint comparisons.
- Six host analyzer tests, plus a preserved reference binary/ELF/config/hash set.

Instructions and the exact measurement contract are in
[`tools/benchmark_3ds/README.md`](../../tools/benchmark_3ds/README.md).

The original game update and draw functions still execute. Draw-side mutations
are retained. Bypass removes the graphics task and its fallback presentation;
it does not eliminate command generation, native frame/platform work, scheduling,
asset loading or audio. All hooks are excluded from the ordinary build by default.

## Validation receipts

The accepted local runs are `gp-render-b`, `gp-render-c` and `gp-bypass-a` under
ignored `experiments/local/m0/`. They used the same diagnostic `.3dsx` SHA-256:

`90fe38208459d5aa32be26b8b39f1d669b2380319df511510a5ff98f7c8a2638`

| Comparison | Result |
|---|---|
| Rendered B → rendered C repeat | All 1,000 selected state/RNG fingerprints matched |
| Rendered B → graphics-task bypass A | All 1,000 selected state/RNG fingerprints matched |
| Race coverage | All captures: mode GP, course 0, 30 racers, ticks 0–999 |
| Emulator diagnostics | No unmapped-memory entries or script timeouts in the accepted runs |
| Ordinary build | Builds with the benchmark feature disabled; existing three host suites passed |

Fingerprints cover selected racer positions/velocities/speed, IDs/status flags,
lap/race position/time, mode/course/count and both gameplay RNG streams. They do
not cover every AI/energy/camera/audio/save field. This is a useful regression
signal, not proof of complete gameplay equivalence or full-lap correctness.
Race initialization deliberately resets seeds and the game frame counter for
this test. That setup is identical in both paths and is not a production change.

## What the captures say

The rendered reference's p95 update interval was about 0.419 ms and its p95
original draw-generation interval about 0.362 ms in the emulator's tick clock.
The bypass's corresponding intervals were about 0.418 / 0.362 ms. Rendered graphics
task elapsed time includes GPU/driver waits; it must not be labeled pure CPU work.

**These values are not calibrated OG ARM11 costs and cannot establish achievable
OG FPS or the speedup of a future native renderer.** Their immediate value is that
we can attribute stages and compare an identical captured simulation window.
The capture includes race initialization as its first sample; raw CSVs retain
that loading spike. No claim of a steady-state maximum or individual crowd view
is derived from the 30-racer count alone.

| End-of-capture memory | Rendered B | Bypass A |
|---|---:|---:|
| Ordinary live heap | 42.278 MiB | 39.607 MiB |
| Allocated linear heap space in use | 7.998 MiB | 3.044 MiB |
| Reserved linear heap | 32 MiB | 32 MiB |
| Diagnostic capture array (BSS, already in image) | 0.5625 MiB | 0.5625 MiB |

This is an end snapshot, not peak or total process memory. Image/BSS, other runtime
allocations, transient transition peaks and VRAM need separate accounting. The
emulator used the New3DS 124 MiB application profile; libctru reserved that process
budget across image and heaps. The regular heap's live usage still exceeds the
ordinary-heap allocation expected from the default OG split. Removing rendering
tasks alone does not solve the port's memory architecture.

## Findings that changed the plan

1. **Renderer-owned pacing is a runtime dependency.** An early bypass ran thousands
   of host loops before title/audio state advanced. Explicit shared vblank pacing
   is required for the diagnostic A/B; the old unpaced result is invalid.
2. **Attract mode was not a sufficient deterministic oracle.** Rendered repeats
   diverged late (around ticks 2095–2097), and a paced bypass entered its demo at a
   different game tick. The root cause of that longer-sequence divergence is not
   established. The accepted GP fixture replaces attract mode, with declared
   controlled initial state and coverage guards; it does not claim to fix it.
3. **Visual LOD is coupled to gameplay.** In `Racer_ReceiveDamage`, `machineLod == 0`
   can keep an otherwise destroyed opponent alive at energy 0.1. Other LOD checks
   gate effects that advance shared RNG. The native architecture now requires an
   original-rule gameplay classification separate from visual detail/draw distance,
   and a separate random stream for added visual effects.

## Next gates

The next native rendering slice is a small independent lit indexed-mesh harness
with camera-relative track geometry, followed by a 30-machine scene. Validate
coordinate precision, materials, clipping and submission ownership on target.
The current controlled gameplay fixture can later compare integration against
the retained game, with wider state coverage and longer driving replays.

Before claiming OG feasibility, measure actual OG simulation/audio timing and
memory fit, implement the native scene path, and run the integrated full-quality
race there. The current legacy benchmark may itself exceed OG memory; that does
not substitute for testing the smaller native rendering harness.

M0.5 extends this infrastructure with a separate bounded, poll-exact full-session
replay stream and results-verified oracle. See [M0.5 race replay](m05-race-replay.md).
Full manually driven race repeatability remains a separate acceptance gate.
