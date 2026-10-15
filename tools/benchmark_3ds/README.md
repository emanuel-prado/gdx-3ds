# M0: reference gameplay and graphics-task bypass

This is opt-in diagnostic infrastructure for the
[native runtime plan](../../docs/NATIVE-3DS-ARCHITECTURE.md). It retains original
game update **and draw generation**, while optionally bypassing graphics task
translation/interpretation/submission. It is not a native renderer or a pure
simulation-only executable.

## Build and capture

Use the initialized/patched checkout and toolchain from
[local setup](../../docs/LOCAL-SETUP.md). Converted archives and the user's DSP
firmware must already be staged in the ordinary isolated Azahar profile.

```sh
bash tools/dev.sh benchmark-build
python3 tools/benchmark_3ds/run_m0.py reference-a --mode render
python3 tools/benchmark_3ds/run_m0.py reference-b --mode render
python3 tools/benchmark_3ds/run_m0.py task-bypass --mode bypass
python3 tools/benchmark_3ds/analyze_m0.py \
  experiments/local/m0/reference-a/benchmark.csv \
  --compare experiments/local/m0/reference-b/benchmark.csv
python3 tools/benchmark_3ds/analyze_m0.py \
  experiments/local/m0/reference-a/benchmark.csv \
  --compare experiments/local/m0/task-bypass/benchmark.csv
python3 -m unittest discover -s tools/benchmark_3ds -p 'test_*.py'
```

The benchmark build uses `build-3ds-benchmark/`, leaving the ordinary reference
build intact. Each run creates a fresh profile under `experiments/local/m0/LABEL/`;
an existing label is rejected. Input archives/firmware are linked read-only by
the application, and saves/configuration are separate per run. Labels, binary
and asset hashes, seed values, source hashes, CSVs and emulator logs are retained
locally. The runner needs Python 3.11+, Azahar desktop access and a working GPU.

The current scenario navigates title → GP/difficulty → Jack Cup → machine → engine
settings, then accelerates straight ahead in the first course with 30 racers.
This is a controlled race-start scenario, not a full-lap driving replay.
Report actual mode/course/racer coverage from the CSV; merely starting Azahar is
not proof that the race was reached. The default capture is 1,000 **GP** game ticks;
menus are excluded. Menu timeouts and unexpected course/racer coverage fail the run.
`--frames` and `--timeout` override the sample count and wall-time limit.
Do not run compilation or other benchmarks concurrently when collecting timings.

Two early 3,000/2,300-tick rendered-repeat experiments diverged late in an attract
sequence (first aggregate differences around ticks 2095–2097), despite identical
gameplay RNG fingerprints at that boundary. The first 2,000 selected states matched
across those repeats. Paced bypass also entered the demonstration at different
game ticks. Those attract captures are not the accepted A/B scenario. The current
race-only mode resets both RNG streams and the game frame counter immediately
before `Race_Init`, equally for both paths. This is a declared test initial state;
it does not establish that unmodified attract-mode determinism is fixed.
`--through-tick` explicitly
selects a shared window in the analyzer; reports must disclose using it.

## Captured sections

The diagnostic target uses linker wrapping at existing external call boundaries,
without modifying the pinned decomp source:

| Section / field | Meaning |
|---|---|
| `update_us` | Elapsed `func_800690FC`, including mode update/init/transition work |
| `draw_us` | Elapsed `func_80069698`, including N64 command generation and original draw side effects |
| `gfx_us` | Elapsed synchronous `gdx_gfx_run`; includes its waits, not just graphics CPU instructions |
| `tasks` | Graphics tasks assigned to this sample; the final sample may have zero tasks during requested shutdown |
| `state_hash` | Selected racer IDs/flags, segment position, world position, velocity, speed, race time, lap and race position |
| `rng_hash` | Both gameplay random seeds and masks |
| Split hashes | Position, velocity, status and race-clock categories for localizing divergence |
| `vi_tick` | Absolute VI counter, diagnostic only; boot VI offset may differ |

Each row is captured immediately after game draw generation. Main-thread update,
draw and graphics sections are not nested in one another. Timing reads include
fiber yields and OS/audio preemption. They are **elapsed times, not isolated thread
CPU time**. Audio continues running in both modes, but its synthesis CPU cost is
not separately measured by this first slice.

Both modes force sequential rendering, mono and the original rival-detail policy.
They use one explicit vblank wait in the host loop and disable the renderer's
duplicate pacing wait. An earlier unpaced bypass completed thousands of ticks
before title/audio state could advance; its results are invalid as a race A/B.
Native frame begin/end and platform/UI work remain in the diagnostic executable.
Bypass mode is intended to show a blank/stale game image.

The sample array is fixed-size (8,192 entries; current build 589,824 bytes). No
CSV is written during capture. On completion, main requests orderly shutdown,
writes to a temporary CSV, and renames it only after successful close. The runner
rejects partial captures. `samples`, timing percentiles and grouped race coverage
are derived from those rows; they are not watchdog five-second FPS samples.
Percentiles use sorted index `floor(p * (n - 1))`.

The comparator requires equal lengths and matching tick/mode/course/racer and
selected state/RNG fingerprints. It ignores timing values and the absolute VI
offset. Matching hashes are a regression signal for the selected fields, not proof
of complete gameplay equivalence: energy, every AI field, camera, audio and save
state are not all fingerprinted. Cross-platform floating-point equality is not
assumed.

## Memory and interpretation limits

The CSV footer records ordinary heap capacity/live/free bytes, linear heap
capacity/free bytes and capture-array size after measurement. Emulator log receipts
also report process commit limit/current use at pre-gfx boot and at shutdown.
Pre-gfx `linearFree=0` reflects the linear allocator not being initialized yet;
it must not be read as allocation exhaustion. Include the fixed capture array in
diagnostic image/BSS accounting, rather than adding it to `heapUsed`.

The emulator's New3DS default application limit is used by this runner. Its tick
timings and GPU waits are not calibrated OG ARM11 measurements. **Do not multiply
these timings by a clock ratio, infer achievable OG FPS, or claim native-renderer
speedup from this bypass.** Real OG timing and memory-fit gates remain open.
Any comparison that fails the state or race-coverage check is invalid for speedup
claims.

For physical testing, the same opt-in `.3dsx` reads `[benchmark] mode=1` (render)
or `mode=2` (bypass), plus `race_only=1` and `frames=1000`, from the existing game
INI. Copy a generated run's `benchmark-input.txt` to
`sdmc:/3ds/gdiffuser/benchmark-input.txt` and use the same fresh-save initial state.
Archive `benchmark.csv` before the next run. The current legacy runtime is still
New3DS-oriented and may not fit normal OG memory; this infrastructure does not
remove that blocker. Back up baseline saves/configuration before hardware use.

## Source findings relevant to native migration

`Race_Draw` modifies a transition counter. `Racer_Draw` writes LOD/visibility state
that later gameplay reads. `Racer_ReceiveDamage` keeps a zero-LOD racer alive with
energy 0.1 when damage would otherwise destroy it; LOD also gates effects using
shared RNG. Native rendering must preserve that original gameplay classification
separately from visual LOD and extended draw distance. The native plan now records
this requirement explicitly.
