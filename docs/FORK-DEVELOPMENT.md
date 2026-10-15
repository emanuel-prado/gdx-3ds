# Working in this experimental fork

This fork is `emanuel-prado/gdx-3ds`; the original port is
`cruxxxxxx/gdx-3ds`. Upstream's New3DS results do not establish original 3DS
compatibility. See [the investigation](research/og3ds-bottlenecks.md).

## Repository routing

Run once in each clone:

```sh
bash tools/setup-fork.sh
git switch -c experiment/my-idea
```

The setup script checks the fork URL before changing **local** Git settings:
plain pushes target `origin`, new branches automatically establish their upstream
on first push, `gh` defaults to the fork, and `upstream` has a disabled push URL.
Fetching upstream still works. These settings are not copied by Git clones, which
is why the script is tracked. They prevent common routing mistakes; an explicit
URL or `gh --repo` can override them.

```sh
git remote -v
gh repo set-default --view
git fetch upstream
git push -u origin HEAD
```

Use `gh ... --repo emanuel-prado/gdx-3ds` when specifying a repository explicitly.
Keep experiments on `experiment/*`; integrate upstream through a separate branch
and review the diff before merging. Submodules retain their original URLs and
pinned commits: do not push port changes to those repositories. Store changes to
`decomp` and `libultraship` in the ordered patch stack described in
[`port/3ds/patches/README.md`](../port/3ds/patches/README.md).

## Fast local checks and remote builds

For the installed Linux Docker toolchain and isolated Azahar launcher, see
[local setup](LOCAL-SETUP.md).

The portable checks need a C/C++ compiler and only one pinned submodule:

```sh
git submodule update --init --depth 1 decomp
bash tools/test-host.sh
```

They run the existing pointer packing, display-list conversion, and SD/archive/save
checks in a disposable temporary directory. They need no ROM or devkitPro and
do not measure console performance. `Experiment checks` runs them on pushes to
`experiment/**`, pull requests, and manual dispatch, with a read-only token.

For a console build, initialize all submodules, install devkitPro as described in
[`3DS-HARDWARE.md`](3DS-HARDWARE.md), then run:

```sh
git submodule update --init --recursive
bash tools/ci-3ds.sh --jobs 4
```

This applies the patch stack to submodule working trees. Review local submodule
edits before running it; do not use `SKIP_PATCH_GATE=1` for a clean baseline.
The full build/emulator helper still contains macOS-specific emulator paths;
the portable checks above work on Linux independently.

On your fork, manually dispatch `Release (3DS)` to build console binaries and
extractors as Actions artifacts. Leave `publish` unchecked. A `v*` tag also builds
artifacts, but no longer publishes a release. Publishing requires manual dispatch,
`publish=true`, a nonempty tag, and an existing release **in the repository running
the workflow**. Only that job receives release-write permission. This work has not
pushed a branch, triggered Actions, or uploaded a release.

## Protect game data during console experiments

Use a separate emulator profile / virtual SD for experiments. On hardware, back up
the entire `sdmc:/3ds/gdiffuser/` directory before running an experimental binary.
Keep the baseline binary, its matching ELF, INI, and logs alongside that backup on
your PC. Use a clearly named experimental `.3dsx` through the Homebrew Launcher.

**Renaming the executable does not isolate saves or configuration.** The game
still reads/writes `sdmc:/3ds/gdiffuser/`, including `saves/`, `gdiffuser.ini`, and
rotating logs. The CIA still has upstream's title ID `000400000FF3D500` and would
replace that installation. Use `.3dsx` for initial experiments; do not install the
experimental CIA over a baseline you want to retain. A future parallel-install
build needs both a distinct title ID and separate runtime data paths.

Build directories, local `experiments/local/` notes, host `sdmc:/` fixtures,
`gdiffuser.ini`, saves, ROMs, and converted archives are ignored. Check
`git diff --cached --stat` before committing; never force-add game data.
