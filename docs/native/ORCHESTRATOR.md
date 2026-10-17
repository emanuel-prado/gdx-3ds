# Native port campaign

Updated 2026-10-17. Core status: **unqualified; implementation in progress**.
Integration branch: `dev/native`, M1a merge `eb8fea2` (PR #1, implementation
`9b3c520`). Preserve the ordinary legacy reference executable throughout.

| Slice | Status | Owner / worktree / PR | Evidence / next gate |
| --- | --- | --- | --- |
| M0 controlled oracle | Validated emulator-only | Existing implementation | 1,000 selected fingerprints; physical timing open |
| M0.5 session oracle | Implemented, acceptance open | Read-only test agent | Human unfinished `manual-race` preserved; inspect valid prefix, never relabel complete |
| M1a Blue Falcon LOD2 | Integrated; hardware-pending | PR #1 | Independent review, fresh host/build/Azahar pass below |
| M1b texture compiler | Running | Asset agent `/tmp/gdx-native-m1b`, `experiment/native-3ds-m1b-textures` | Extract complete tile catalog and native RGBA8 layout; host gate first |
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
2. Finish the isolated M1b texture compiler, run synthetic and real-archive tests,
   independently review output byte order/layout and tile coverage, draft PR to
   `dev/native`, integrate only its bounded host gate.
3. Implement native texture/material sampling with preserved M1a harness and
   explicit format/version boundary; validate matching-camera visual captures.
4. Inspect manual-race diagnostic prefix report; repair any demonstrated oracle
   endpoint/control defect before asking for a replacement fixture.

Do not infer agents are running after the session ends. Reassign these concrete
steps if interrupted. All hardware, full-race and full-game gates remain open.
