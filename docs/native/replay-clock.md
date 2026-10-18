# Full-session bypass boot divergence

The repaired results predicate does not solve full-session bypass equivalence.
The unchanged preserved human input matches between two independent rendered
cold boots for 8,236 input/state polls through results. Bypass differs at poll
126, before gameplay: mode and RNG, then game tick at poll 127.

Source audit identifies a wall-clock boot dependency. The patched USA boot hold
in `decomp/src/sys/sys_gfx.c:755` yields until `osGetTime()` advances about
230/60 = 3.833 seconds. On 3DS, the game clock aliases
`gdx3ds_osGetTime()` in `port/3ds/lus_glue/gdx3ds_libultra.cpp:59`, which reads
`std::chrono::steady_clock`. The hold ends at rendered poll 126 versus bypass
poll 241. Each respective title entry has the same RNG fingerprint 3927072910
and mode 32768. Boot work and input-poll cadence differ, so an identical poll
index does not imply the same elapsed boot time. The first-difference report
remains under ignored `experiments/local/replay/endpoint-fixed-bypass-a/`.

This is evidence of timing dependence, not proof that no other bypass divergence
exists after boot. External benchmark pacing already bypasses the profiler's
presentation wait (`gdx3ds_gpu_prof.c`); a duplicate-wait fix has not been proved.
No wait was removed speculatively and no fixture prefix or race state was reset.

A proposed deterministic VI-only clock is not implemented. The original game
also busy-waits on `osGetTime()` (`game.c:702`); a clock advancing only at host
VI servicing could deadlock that path. Changing the diagnostic clock also
changes fixture identity and cannot silently reinterpret the existing recording.

Exact next oracle task: instrument the game-clock reads and boot/yield/poll
boundaries with bounded recording, establish the cadence cause, and implement a
versioned replay time contract (recorded clock events or a validated explicit
virtual-time policy). Preserve production timing and legacy fixture rejection.
Then record/replay complete required input coverage and repeat bypass comparison
from cold boot. Native renderer work remains independent of this open gate.
