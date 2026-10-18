# Native port campaign

Updated 2026-10-17. Core status: **unqualified; implementation in progress**.
Integration branch: `dev/native`, base `83a561f` after PR #5. M1a merged in
`eb8fea2` (PR #1, implementation `9b3c520`). Preserve the ordinary legacy
reference executable throughout.

| Slice | Status | Owner / worktree / PR | Evidence / next gate |
| --- | --- | --- | --- |
| M0 controlled oracle | Validated emulator-only | Existing implementation | 1,000 selected fingerprints; physical timing open |
| M0.5 session oracle | Endpoint repaired; bypass failing | PR #4 integrated; `/tmp/gdx-native-bypass` diagnosis | Two rendered cold prefixes match through results; bypass diverges at poll 126 before race; full acceptance open |
| M1a Blue Falcon LOD2 | Integrated; hardware-pending | PR #1 | Independent review, fresh host/build/Azahar pass below |
| M1b texture compiler | Integrated | PR #3, `26646c4` | 25 tests, independent review; eight tiles, 18,432 GPU bytes; native sampling pending |
| M1b native texture upload | Integrated | PR #5, merge `83a561f` | Two 120-frame pixel runs pass; runtime corruption rejected before upload; hardware pending |
| M1b textured machine diagnostic | Validated; preparing PR | Integrator `experiment/native-materials-integration`; source `41ff400` | 360 frames; 4,608 material samples error ≤1; unknown recipe rejected; shade/FLX fidelity pending |
| M1b native materials/lighting | Pending | Integrator | Runtime sampling + exact material/FLX semantics + reference comparison |
| M1c/M1d | Pending | Unassigned | Families/LODs/crowd and procedural course geometry |
| M2–M7 | Pending | Unassigned | See architecture; no full-game or hardware acceptance claimed |
| M8–M10 optional | Deferred | Owner creative inputs later | Original cartridge port first |

## Independently reproduced M1a gate

- `bash tools/test-host.sh`: three portable C/C++ suites, 21 M0/M0.5 tests,
  13 native pack tests pass; loader exercised with UBSan.
- `bash tools/dev.sh native-build`: existing Docker toolchain build passes.
- `python3 tools/native_assets/compile_machine.py --archive dist/sdmc/3ds/gdiffuser/fzerox.o2r`:
  8,872 bytes, 218 vertices, 288 indices, eight materials; SHA-256
  `dde03572da88c7fe0aaae1db5128aec89c3a55637af1330cc58b6fce0b8efa98`.
- `python3 tools/native_assets/run_azahar.py review-m1a-20261017`: 720 frames,
  exit 0, depth-order captures equal, 14 near-plane crossing triangles.
  Receipt: ignored `experiments/local/native-m1a/review-m1a-20261017/`.
  Host process inspection confirmed the test emulator and wrapper exited.
- Independent agent reviewed actual compiler, loader, renderer, shader, original
  recipe, and receipts: no blocking M1a defect. M1a is explicitly an unlit
  standalone mesh, not accurate materials or integrated simulation.
- Emulator median CPU submission 0.451737 ms / previous GPU queue 0.249493 ms.
  These are **not OG hardware costs or sustained presentation deadlines**.
  VBO/IBO 8,424 bytes; command buffer 256 KiB; target 768,000 bytes.
  Heap counters are not total process memory. Physical OG gates all remain open.

## Decisions and risks

- PR #3 compiles all eight texture tiles with original RDP component expansion,
  correcting two inherited legacy importer approximations. See
  [texture evidence](m1b-textures.md). Native materials are still incomplete.
- The original unfinished recording contains a genuine first-place 98.192-second
  three-lap finish. Two incorrectly widened byte-global reads prevented results
  detection. The corrected build reproduces all 8,236 input/semantic snapshots
  through ranking except the now-correct final results word. See
  [endpoint diagnosis](replay-endpoint.md). Diagnostic source/output are partial;
  required boost/combat/pause coverage and full accepted cold replays remain open.
- Both rendered diagnostic cold boots match through results. Full-session bypass
  fails first at poll 126, tick 0 (mode and RNG); investigate startup/task side
  effects without hiding the prefix or resetting game state. The test was closed
  and its first-difference report is preserved locally.

- Bypass boot timing depends on a ~3.833-second wall-clock logo hold: identical
  title-entry mode/RNG occurs at poll 126 rendered versus 241 bypass. See
  [clock audit](replay-clock.md). No fixture prefix was masked or clock changed.
- Textured-machine diagnostic uses eight actual textures, stock initial skin,
  signed-UV shader and two finite native combiners. Declared shade=1/q=0 and
  nearest sampler are not original lighting/filter fidelity. See
  [material gate](m1b-materials.md). 33 native + 22 oracle tests and all three
  portable suites pass; all three standalone native builds pass.
- No display-list interpreter in standalone native harness; original runtime
  retained only as reference. No gameplay/RNG/LOD/save changes in M1a.
- Blue Falcon material tile 0 inherits shared setup texture; include it explicitly.
  G_TEXTURE_GEN has game-specific FLX alpha semantics; audit original microcode
  before substituting generic environment UV generation or ordinary lighting.
- Existing root checkout has user `docs/LOCAL-SETUP.md` edits, untracked AGENTS.md,
  and expected patch-stack submodule modifications. Do not discard or stage these.
- Only private local assets/fixtures/logs; no copyrighted packs or captures in Git.
- Integration authority covers `dev/native`; final release/main still owner-only.

## Human gates

Physical OG console logs are unavailable: bundle renderer, memory, lifecycle and
later full-race/soak checks when a meaningful hardware candidate exists.
User authorized use of unfinished recording on 2026-10-17; inspect it first before
requesting another drive. Full race equivalence requires real completion and cold
replays; partial data can only support diagnostic prefix work.

## Recovery / exact next task

1. Check remote `dev/native`, open PRs and `git worktree list` before resuming.
2. Open/integrate the validated material diagnostic PR after CI. Implementation
   `41ff400` is independently reviewed and GPU-tested; all test emulators closed.
3. Next executable graphics task: original directional/ambient vertex lighting
   plus FLX LUT-derived vertex alpha and highlight blending. Read the precise
   [material audit](m1b-material-audit.md), compile private LUT data from verified
   source inputs, and test GPU output against known normal/light/LUT vectors
   before matching-camera comparison. Keep the unlit diagnostic available;
   do not use it as an unsupported-material fallback.
4. Diagnose the observed poll-126 full-session bypass divergence in the isolated
   bypass worktree; retain explicit partial-data labels and originals.

Two implementation agents hit a service usage limit; their material work was
finished serially by the integrator with a separate review agent. Their proposed
bypass clock change was not implemented. Do not infer agents are running after
the session ends. Reassign these concrete
steps if interrupted. All hardware, full-race and full-game gates remain open.
