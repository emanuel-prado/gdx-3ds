# Original 3DS feasibility investigation

Date: 2026-10-14. Baseline HEAD: `535cf40297a0`. Scope: source audit and analysis of measurements already checked
into this fork. **No original 3DS performance was measured in this investigation.**

## Conclusion and evidence limits

The current port depends on New3DS CPU throughput, its spare rendering core, and
its larger application memory region. The first engineering gates are memory
fit and the sequential CPU budget. Lower resolution alone is unlikely to solve
either. Original 3DS support is still unproven, including boot and sustained play.

This checkout initially had no submodules, devkitPro, CMake, emulator, ROM, or
on-device logs. The pinned decomp headers were fetched and the existing portable
tests were run with the host compiler. Those checks validate port invariants, not
hardware speed. A deterministic game performance feedback loop could not be run
here. Consequently this document proposes falsifiable experiments instead of
claiming a reproduced regression or a validated performance fix.

The main timing source is
[`source-perf-data.md`](../postmortem/source-perf-data.md), especially sections 1,
2 and 6. It records earlier hardware runs and their build hashes, and explicitly
distinguishes emulator results. Its referenced `/tmp/hw-art-*` raw logs are not
present in this checkout. These are historical New3DS measurements, not new
measurements of HEAD. Do not combine deltas across different rounds as an A/B.

## Hardware budget

| Resource | Original 3DS | New3DS target | Consequence |
|---|---|---|---|
| ARM11 application CPU | ~268 MHz, no New3DS L2 | ~804 MHz plus optional 2 MiB L2 | A clock-only model costs 3x CPU time before cache effects |
| Dedicated extra render core | No core 2 | Core 2 available | Current render worker falls back to sequential execution |
| Typical application commit region | 64 MiB | 124 MiB | Code, ordinary heap and linear heap must share this budget |
| Physical FCRAM | 128 MiB | 256 MiB | Physical capacity is not the application's allocation budget |

Hardware reference: [3dbrew hardware research, mirrored by Mikage](https://docs.mikage.app/Hardware/).
Memory modes are tabulated in the existing
[`3ds-memory-budget.md`](3ds-memory-budget.md) with references to 3dbrew. Original
3DS extended modes can change the application region (up to 96 MiB), but require
deliberate packaging/launch validation and do not increase CPU throughput.

## 1. Memory fit is an independent blocker

Current source confirms:

- `port/n64_rdram.h` / `port/decomp_port.c`: a 16 MiB emulated RDRAM allocation.
- `lus-resource-cache-cap.patch`: a 24 MiB **payload** cache budget. Externally
  referenced resources are pinned and may exceed it; map nodes, strings, and
  allocator overhead are not included in that payload accounting.
- `port/3ds/gfx/gfx_citro3d.cpp`: a 1 MiB linear VBO pool, plus textures, command
  buffers and render targets.
- `port/n64_sched.c`: 128 KiB per game fiber on 3DS. The older planning document's
  1 MiB-per-fiber warning has already been addressed.
- [`heap-watch.md`](heap-watch.md): a prior hardware session's ordinary heap grew
  from 40.8 to 50.2 MB over 37 minutes. This suggests memory pressure; it does not
  establish a leak or the footprint of the current build.

The old static budget's ~80 MB estimate is a planning artifact: do not present its
estimated linked code size or 16 MiB texture pool as current measurements. The
cache is now capped and stacks have already been reduced.

There is a second constraint beyond total bytes: the heap split. No port override
of `__ctru_heap_size` / `__ctru_linear_heap_size` was found.
[libctru's allocator](https://github.com/devkitPro/libctru/blob/master/libctru/source/system/allocateHeaps.c)
subtracts current commit from the process limit and splits the rest, preferring
a 24 MiB ordinary heap and capping the linear heap at 32 MiB. At a 64 MiB process
limit this policy cannot provide the 40.8 MB ordinary heap reported in that
session, even before adding linear allocations. Verify the allocator revision
actually linked by devkitPro before choosing explicit heap sizes.

First measure linked text/rodata/data/BSS, process commit limit/current usage,
ordinary heap capacity/high-water, linear capacity/high-water, and VRAM use.
`heapUsed` is not total process memory; `[mem-census] lin=` is **linear free bytes**,
not linear usage. Avoid double-counting caches already inside `heapUsed`.
Use heap-watch owner attribution to distinguish cache fill from retained growth.

## 2. Display-list interpretation dominates the measured CPU work

Historical same-course New3DS crowd data, campaign levers on, profiler on:

| Exclusive CPU bucket | ms/frame | Share of these six buckets |
|---|---:|---:|
| `dsp`: display-list RUN remainder | 7.84 | 42% |
| `tri`: triangle handling | 4.64 | 25% |
| `br`: graphics bridge / translation | 3.07 | 16% |
| `drw`: draw submission | 1.24 | 7% |
| `vtx`: vertex handling | 1.18 | 6% |
| `imp`: texture import | 0.78 | 4% |
| Sum | 18.75 | 100% |

Source: hardware log `hw-art-1788386194/log.txt` summary, 45 crowd windows.
Rounded source total is 18.8 ms. `dsp` is **not audio DSP time**: the profiler
header defines it as dispatch plus handlers not attributed to other sections.
The section profiler subtracts children. `[profop]` handler times may contain
nested sections, so do not add them to this total.

The remaining work is around repeated N64 state interpretation, triangle
clipping/emission, and bridge conversion. Existing optimizations already include
flat dispatch, triangle/state memos, packed VBO emission, TMEM fast paths, HUD
atlas batching and bridge memos. Proposing these as new optimizations would
repeat completed work. Use opcode and triangle-phase censuses to find the
remaining misses before changing them.

As a **clock-only illustration**, 18.75 x 3 = 56.25 ms of this graphics CPU work
on OG hardware, before logic/audio and cache differences. This is not an FPS
prediction. Reaching a 16.7 ms budget would require about 70% less work than that
model; even a 33.3 ms budget requires about 41% less. Actual measurements may
differ substantially, including profiler overhead.

## 3. OG loses the parallel path that helped New3DS approach 60

`gdx3ds_renderthread.cpp:gdx3ds_rt_init` checks `APT_CheckNew3DS` and explicitly
selects sequential rendering on original hardware. There is already a fallback;
there is no missing switch that unlocks a spare OG rendering core.

Historical New3DS round 5 reached median 59.6 fps, p10 51.4 with ahead rendering,
bridge-on-main and automatic rival detail. That result does not describe the OG
fallback. It also does not describe every fresh INI: current code defaults
`debug.renderthread` to **1 (pipe)**, while round 5 explicitly used **2 (ahead)**.
The report lacks per-bucket hardware receipts for that final ahead run.

Do not multiply its pipelined FPS by a clock ratio to estimate OG performance.
First compare the same New3DS binary with `renderthread=0`, `1`, and `2`, restarting
each run. Then profile sequential execution on real OG hardware.

## 4. GPU fill and audio are secondary hypotheses

Earlier traced hardware GPU times were ~5.1–5.5 ms while CPU work exceeded a
60 Hz budget. That favors CPU optimization first for those scenes. GPU time
overlaps CPU execution and must not simply be added to the CPU bucket sum.
Check `wP3D` (GPU queue wait), `gpu`, draw count and command usage on OG before
concluding the GPU has headroom there. Stereo-off reduces repeated GPU draws,
but the backend reuses the same packed vertices for the two eyes; it does not
halve all interpreter or game work. Stereo is already off by default.

Audio still matters for deadline misses at lower CPU throughput. The drain thread
tries core 2 on New3DS, then a granted share of system core 1, then core 0.
That last fallback competes with game/render work on OG. Audio's separate
hardware DSP does not run the Fast3D `dsp` bucket. Capture producer tick times,
ring minima and underruns; do not attribute graphics dispatch time to audio.

## Ranked hypotheses and experiments

These are predictions to test, not newly confirmed causes:

1. **Memory fit:** if heap capacity is the first gate, boot or mode transitions
   fail with exhausted ordinary/linear capacity. Smaller measured cache/texture
   working sets and a deliberate heap split should change that outcome. Test a
   full course/mode cycle and long soak, not just the title screen.
2. **Sequential CPU work:** if interpreter/bridge work dominates on OG, traced
   `dsp+tri+br` should remain the largest CPU group with `renderthread=0`, and
   minimal rival detail should lower its time and opcode/triangle counts.
3. **Loss of overlap:** if parallelism explains much of the gap, the same New3DS
   workload should slow substantially from mode 2 to mode 0. This isolates the
   worker benefit without conflating it with OG clock/cache differences.
4. **GPU fill:** if fill is the main limiter, mono or a reduced render target
   should lower `gpu`/`wP3D` and improve frame time while CPU buckets stay similar.
5. **Audio scheduling:** if shared-core contention causes stalls, slow frames
   should correlate with producer overruns/underruns and the selected core.

## Repeatable console feedback loop

1. Keep a baseline binary and ELF. Record commit/build ID, hardware model, launch
   format, CPU/L2 configuration, memory mode, INI, course, racer, and fixed input
   sequence. Preserve the original saves as described in
   [fork development](../FORK-DEVELOPMENT.md).
2. Start with mono, sequential rendering, HLE audio (`audio.lle=0`), native rival
   detail and auto detail off. Merge these keys into the INI; preserve bindings:

   ```ini
   [stereo]
   enabled = 0
   [audio]
   lle = 0
   [perf]
   rival_detail = 0
   rival_detail_auto = 0
   [debug]
   renderthread = 0
   filelog = 1
   filelog_max_kb = 8192
   gputrace = 0
   verbose = 0
   ```

3. Run title → selection → same GP start/crowd → steady race → course change.
   Repeat each comparison at least three times after a consistent warm-up.
   Record untraced FPS and audio behavior; then repeat with `gputrace=1` for
   attribution. Trace has a known performance tax. Enable `tri2census=1` only
   for a short targeted probe (its additional hot-path tick reads also cost).
4. Archive `log.txt` **before the next launch** rotates it. The watchdog sleeps
   nominally five seconds: `frame(+delta)/5` is an approximate five-second FPS
   average, not an individual-frame percentile. Use timestamps/actual elapsed
   time when available, exclude suspend/boot/mode changes, and label p10 as a
   percentile of watchdog windows. For `[prof]` means, weight by `n`; `[prof!]`
   is an overlapping subset, not additional samples. Compare crowd windows by
   `vtxN` (historical band 800–1400), because batching changes draw counts.
5. Change **one** variable per A/B: rival detail 0→2; renderthread 0→1→2 on
   New3DS; then clock/cache experiments. This port calls
   `osSetSpeedupEnable(true)` at audio startup and after resume, so a New3DS
   low-clock experiment must explicitly disable both requests. A low-clock
   New3DS remains a proxy with different memory/cache/core behavior.
6. Establish memory headroom, no allocation failures, correct graphics, full-speed
   game simulation, stable audio, and a long-session plateau before claiming
   support. A 30 fps mode requires deliberate simulation/presentation pacing;
   merely skipping ticks could slow gameplay. The current MINIMAL detail tier
   protects the player and five nearest rivals and still simulates the pack.

After memory fit, prioritize eliminating repeated command interpretation and
conversion, then reduce rival geometry/effects further if measurements justify
the visual tradeoff. Native PICA representations / cached immutable geometry are
larger architectural experiments with invalidation and visual correctness costs.
Resolution changes come after a measured GPU bottleneck. A validated 30 fps
presentation mode is a separate design decision, not a promised compatibility fix.
