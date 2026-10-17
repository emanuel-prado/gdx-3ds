# M0.5 full-race replay oracle

Status: implementation and host/cross-build validation; full manually driven race
repeatability is a remaining acceptance gate. This does not implement a renderer,
change physics or AI, or claim complete simulation equivalence.

## Workflow

Build the opt-in diagnostics (ordinary builds exclude all replay hooks):

```sh
bash tools/dev.sh benchmark-build
python3 -m unittest discover -s tools/benchmark_3ds -p 'test_*.py'
```

Record in a new isolated profile, using the existing local assets/DSP firmware:

```sh
python3 tools/benchmark_3ds/run_replay.py experiments/local/replay/manual-race
```

Play normally with Azahar's controls. Navigate from boot into a single-player GP,
complete all three laps, then allow the GP ranking/results screen to appear.
The game exits automatically after that screen has advanced 30 draw calls. The
runner saves `capture.gdr`, `manifest.json`, `report.json` and emulator logs.
Do not close the emulator early: an early clean guest exit has an incomplete
footer; a crash/kill leaves `.tmp` without a final committed capture. Neither
qualifies as a fixture. Increase `--timeout 3600` if needed. The default is 1800
wall seconds; wall time is used only for the watchdog.

Validate the recording, including the metadata digest and race outcome:

```sh
python3 tools/benchmark_3ds/replay.py experiments/local/replay/manual-race/capture.gdr
```

Replay twice, each from its own cold boot, without touching the controls:

```sh
python3 tools/benchmark_3ds/run_replay.py experiments/local/replay/repeat-a \
  --fixture experiments/local/replay/manual-race
python3 tools/benchmark_3ds/run_replay.py experiments/local/replay/repeat-b \
  --fixture experiments/local/replay/manual-race
python3 tools/benchmark_3ds/replay.py experiments/local/replay/repeat-a/capture.gdr \
  --compare experiments/local/replay/repeat-b/capture.gdr \
  --report experiments/local/replay/repeat-comparison.json
```

Each replay automatically compares its entire capture to the selected fixture.
Exit status is nonzero for mismatch, bad metadata, malformed/truncated files,
incomplete playback, timeout or failure to reach the expected race endpoint.
`report.json` reports the first differing poll, game tick, subsystem, reference
and candidate values. Hash values are unsigned 32-bit integers. To compare another
executable, pass `--binary /absolute/path/to/candidate.3dsx`. Executable SHA-256 is
provenance, deliberately excluded from configuration identity. Candidate builds
must implement the same replay protocol and semantic schema.

Graphics-task bypass remains available while preserving game draw side effects:

```sh
python3 tools/benchmark_3ds/run_replay.py experiments/local/replay/bypass \
  --fixture experiments/local/replay/manual-race --graphics bypass
```

The original `run_m0.py`, `analyze_m0.py`, fixed capture and race-init reset remain
separate and keep their original contract. Do not combine `[benchmark] mode` and
`[replay] mode`.

## Input and state contract

The hook is inside `gdx_controller_poll`, after physical mapping, legacy autoinput
and `GDX_INPUT_SCRIPT` resolution, before controller presence publication,
digital-stick derivation and accumulate/finalize button-edge processing. Replay
overrides all four effective pads and presence bits at that same hook. Recording
with an existing input script is supported; replay rejects a competing script.
All sixteen button bits and signed 8-bit stick values are lossless; no resampling
or quantization is applied. Duplicate game ticks are intentional: every actual
poll, including paused/menu/divided-tick polls, has its own record.

Each record includes the semantic snapshot immediately BEFORE the corresponding
input is processed. A divergence caused by an input is consequently visible at
the following poll. The last snapshot verifies the endpoint through results;
there is no claim to compare simulation after the last recorded input.

The stream covers player and rival positions, velocities, speed, flags, race
clocks, laps and positions; both RNG seeds/masks; energy/max energy, attack,
boost and spin timers, race distance and per-lap times; machine LOD; camera
mode/state/eye/at/FOV and pause; and explicit player completion fields. It never
hashes raw structures, pointers, padding or graphics matrices. LOD remains in
this oracle because `Racer_ReceiveDamage` and stock effects/RNG depend on it.
Bypass skips graphics execution, not `Race_Draw`/`Racer_Draw`. Later renderers must
preserve original gameplay classification and shared RNG consumption separately.

No race-init seed/frame reset is applied to full-session replay. Existing boot
seed pins set RNG1 to seed=12345/mask=24690 and RNG2 to seed=135780/mask=67890.
The manifest fixes archive and firmware SHA-256s, configuration and cold-boot
assumptions. Saves start empty per run and remain profile-local. The emulator
uses the existing New3DS memory profile to fit the current legacy build; replay
code itself requires no New3DS feature or extra core. There is no savestate.

The endpoint requires GP mode, 30 racers, an observed progression through laps
1, 2 and 3, a finished player with positive race time, `lapsCompleted == 4`
(the game's one-based counter after three laps), and the ranking/results screen.
The same GP course must be retained. Finishing position/time are compared, not
merely presence of a finish flag. Crashes, forced early finishes and demos do
not qualify. Fixtures are one race, from boot through its results.

## Wire format and resource bounds

All integers are little endian. Header: six ASCII bytes `GDXRPL`, version byte 1,
one zero byte, followed by 64 ASCII lowercase SHA-256 hex bytes identifying canonical
metadata JSON (`sort_keys=True`, separators `(',', ':')`).

A poll is tag 1 followed by four 5-byte pads (`u16 buttons, i8 x, i8 y, u8 present`)
and twenty `u32` semantic words in `replay.py:FIELDS` order. Size: 101 bytes/poll,
about 355 KiB/minute at 60 polls/sec. Footer: tag 2, `u64 poll_count`, `u32` FNV-1a
of all poll bytes (offset 2166136261, prime 16777619), `u8 complete`. No trailing
bytes are permitted. The count is 64-bit, with no M0 capacity or tick limit.
Unknown tags/versions, invalid presence/boolean values, unexpected EOF, checksum
failures and incomplete footers are errors. Checksums detect corruption, not
malicious modifications; metadata hashes identify local fixtures.

The C stream owns a single pending write and one prefetched read (202 bytes plus
stdio's bounded buffers). It performs no file operations in the poll callback.
`gdx3ds_benchmark_pace`, outside the simulation path on the sequential host loop,
flushes pending records and prefetches the next one. Stdio batches physical I/O.
A second unserviced poll fails rather than dropping an edge. This is deliberately
single-threaded and can stall the host loop on SD I/O; it is a semantic diagnostic,
not a timing benchmark. Read/write/close failures leave an uncommitted `.tmp`.
Future scheduler changes must preserve servicing between polls or replace this
bounded handoff with an explicitly owned queue. Python validation/comparison
also streams with bounded memory, including sessions longer than 8,192 polls.

## Remaining nondeterminism and manual acceptance

The M0 research documented late attract-mode nondeterminism. Full-session replay
includes boot and menus, so boot/scheduler phase and rendering-related RNG remain
unproven over a complete manually driven race. The oracle detects these rather
than masking a prefix or resetting race state. The selected hashes do not cover
every AI scratch value, audio sequencer state or save byte; FNV collisions are
possible. Camera/LOD fingerprints deliberately expose renderer coupling.

To close acceptance: record a successful human-driven GP with steering, boost,
braking, attacks and a pause/resume; validate it; run two independent replays;
require both comparisons to the recording AND their mutual comparison to match
through results; then repeat with graphics bypass and an alternate executable.
Inspect logs for invalid-memory/fatal errors. Preserve local manifests and build
hashes. Exercise an interrupted recording and timeout and verify nonzero status.
Run OG hardware separately before making hardware timing or memory claims.
ROMs, archives, saves, replay files and local artifacts must stay out of Git.

## Validation receipts (2026-10-16)

- 21 host tests pass: the original six M0 analyzer tests and fifteen replay tests.
  They compile the actual C stream with warnings as errors, round-trip 12,000
  polls, verify extreme signed stick values and rapid button changes, preserve
  duplicate ticks, inject over live input, reject malformed/truncated sessions,
  verify metadata/CLI failure, and locate the first divergence even in a
  subsequently truncated candidate.
- Ordinary 3DS game and graphics harness build pass; all three existing portable
  suites pass. The diagnostic `.3dsx` also builds successfully. The ordered
  dependency patch stacks remain unchanged at their pinned submodule commits.
- New Azahar M0 captures `m05-preserve-render-a` and `m05-preserve-bypass-a` under
  ignored `experiments/local/m0/` match for all 1,000 selected fingerprints.
  The rendered capture also matches the preserved `gp-render-b` reference.
- A local protocol experiment recorded boot input and replayed a 300-poll prefix
  twice in fresh Azahar profiles. Both prefixes matched input and all twenty
  selected semantic words exactly. Both guest outputs correctly had
  `complete=0` because there was no race completion. These are **not** accepted
  race fixtures. Receipts are local under `experiments/local/replay-smoke/`.
- An isolated run through `run_replay.py --timeout 3` returned exit status 1
  and a machine-readable timeout report, as expected.
- No human-driven full race was recorded in this session. Full-race repeatability,
  full-race graphics bypass equivalence and original 3DS hardware validation
  remain open. Follow the manual acceptance steps above to close those gates.
