# Manual race endpoint diagnosis

The preserved `manual-race/capture-preserved.gdr.tmp` contains a real three-lap
course-0 GP finish. It is still an incomplete, unaccepted recording. The original
recording, manifest and emulator log were read without modification.

## Evidence

The preserved file is 1,171,456 bytes, SHA-256
`e16d5757890f49a6068c6be178e19f93b9f8cb78702a67d23d7829bb7bae2a4c`.
Its metadata identity validates. Streaming `replay.records(require_race=False)`
yields 10,050 valid polls, then correctly rejects a second GP course. A separate
bounded diagnostic decode finds 11,597 complete poll records followed by a
truncated poll with 86 of 100 payload bytes. No completion footer exists.

| Event | Poll (zero based) | Game tick |
| --- | ---: | ---: |
| 30 racers initialized | 853 | 714 |
| Lap 1 | 1,378 | 1,238 |
| Lap 2 | 3,500 | 3,360 |
| Lap 3 | 5,348 | 5,208 |
| Finished, position 1, 98,192 ms, lapsCompleted=4 | 7,165 | 7,025 |
| Course changes from 0 to 1 | 10,050 | 9,910 |
| Mode becomes GP next course (0x800f) | 10,074 | 9,934 |

Every recorded `results` word is zero. Input masks are only 0, B (0x4000),
A (0x8000), and A+B; ten distinct stick pairs occur before the second course.
This is useful real race and finish regression input, but it does not demonstrate
boost, combat, braking or pause/resume coverage. The pause bit is hashed with
camera data, so its exact value cannot be recovered from that hash alone.

Local machine-readable diagnostics are retained under ignored
`experiments/local/replay/manual-race-audit/`. They explicitly mark partial data
as unaccepted. They do not add a footer or repair original semantics.

## Ranked hypotheses and result

1. **Wrong global ABI widths block the demo-inactive endpoint check.** The sampler
   declared `gTitleDemoState` and `gGamePaused` as `s32`; `game.c` defines both as
   `s8`. The benchmark binary SHA-256 matches the recording manifest
   (`f98dbbca7376fb7d2b2c4b1ab6544c1005be4708b9f8feedb6496e379b8e85e8`).
   Its ELF symbol table places the one-byte `gTitleDemoState` at `0x00476d52`,
   immediately before the four-byte `sBgmChangeLogCount` at `0x00476d54`.
   A four-byte read includes that unrelated counter. Game BGM transitions increment
   the counter. This is a demonstrated ABI defect and the leading explanation
   for an inactive demo failing the endpoint predicate. Exact endpoint timing in
   the original run remains unobserved because the raw result-state/timer globals
   were not recorded.
2. **The hardcoded GP ranking value is wrong.** Falsified by the actual
   `menus.h` enum: `GP_RESULTS_RACE_RESULT` is 1. `menus.c` transitions from top-six
   timing to race-result state, resets the player timer to zero, then increments
   it while drawing the ranking screen. Timer >=30 is an appropriate existing
   threshold; no condition needs to be removed.
3. **The player never completed the race.** Falsified by observed laps 1/2/3,
   the finished flag, position 1, nonzero time, and subsequent next-course state.

## Fix and validation

Only the two extern widths change. All endpoint predicates and wire-format
acceptance checks remain unchanged. The real C sampler is compiled into a host
regression harness with the actual cartridge Racer/Camera definitions and GP
result enums. Correct byte-global definitions precede the sampler, making an
ABI-width regression a compile error. Before the fix this test fails on both
conflicting globals; after the fix all 22 benchmark Python tests pass, including
the real C stream and new sampler regression with UBSan.

The regression also checks top-six timing, ranking timer 29 versus 30, demo state,
wrong lap count, missing finish, incomplete laps, zero race time, wrong mode,
total-ranking transition, and distinct paused/running camera hashes.

```sh
python3 -m unittest discover -s tools/benchmark_3ds -p 'test_*.py'
# An isolated worktree may use the main checkout's patched headers:
GDX_TEST_DECOMP=/path/to/gdx-3ds/decomp \
  python3 -m unittest discover -s tools/benchmark_3ds -p 'test_*.py'
```

## Cross-build and diagnostic replay

The corrected diagnostic `.3dsx` cross-build passes in the existing Docker
toolchain. A fresh cold boot using the unchanged preserved input in replay mode
2 observes `results=1` at poll 8,235, game tick 8,095: course 0, 30 racers,
position 1, race time 98,192 ms and lapsCompleted=4. Comparing all 8,236 input
polls and semantic snapshots to the original yields exactly one difference:
the corrected results word at poll 8,235. The pause/camera hashes happen to match
in this recording; this does not make the old widened read safe.

Receipt: ignored `experiments/local/replay/endpoint-fixed-render-a/`, including
binary/source identities, report and `original-prefix-comparison.json`.
The bounded diagnostic stopped once the freshly generated endpoint was observed;
its capture remains partial and **unaccepted**. No footer was synthesized and
the original recording was not modified. Test process-group cleanup and host
inspection confirmed both the emulator and wrapper exited.

A second independent rendered cold boot, `endpoint-fixed-render-b`, reaches the
same results poll and matches all 8,236 input/state snapshots exactly. Its
immediate cleanup check raced with an exiting child; subsequent host process
inspection confirmed no emulator or wrapper remained, recorded separately in
the local report.

The unchanged input with graphics bypass **fails equivalence**. First differences
are at poll 126, tick 0: mode `32768 -> 0`, RNG fingerprint
`3927072910 -> 951537753`; tick progression differs at poll 127. This is a boot
divergence, not a failure to complete the recorded driving. The test was stopped
once the failure was captured; cleanup and host inspection passed. Receipt:
`experiments/local/replay/endpoint-fixed-bypass-a/render-prefix-comparison.json`.
Do not mask this prefix, insert a race reset, or call full-session bypass accepted.
The controlled M0 race-start comparison has a different initialization contract
and does not override this failure.

## Exact next test

To reproduce the bypass failure, copy the unchanged preserved temporary
recording into a fresh isolated profile as `session.gdr`, with replay mode 2.
Run it under a bounded timeout, monitor the new `capture.gdr.tmp` for the freshly
observed ranking endpoint, then close the test emulator. The source stream will
eventually fail its truncated poll/missing footer if allowed to run to the end;
this is an expected diagnostic failure, never an accepted fixture. Compare
old/new input and semantic words up to the first
expected schema difference (`results`, or the corrected pause hash if old padding
was nonzero). Preserve its provenance as a reconstructed diagnostic run, perform
two independent cold boots and a bypass comparison. Do not treat this as
accepted replay, synthesize the original's footer, or relabel its
all-zero results words. A separate complete fixture covering all required control
actions remains necessary for full M0.5 acceptance.
