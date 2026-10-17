"""Exercise the real game-state sampler with the cartridge's ABI and GP enums."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class EndpointTests(unittest.TestCase):
    def test_real_state_sampler_ranking_transition_and_byte_globals(self):
        decomp = Path(os.environ.get('GDX_TEST_DECOMP', ROOT / 'decomp'))
        # Definitions deliberately precede the real sampler: a widened extern
        # must fail compilation, even if linker padding hides its runtime damage.
        harness = r'''
#include <assert.h>
#include "global.h"
#include "fzx_racer.h"
#include "fzx_camera.h"
#include "fzx_game.h"
#include "src/overlays/ovl_i3/menus.h"
s32 gGameMode, gTotalRacers, gCourseIndex, gRandSeed1, gRandSeed2, D_800CCFB0;
u32 gGameFrameCount, gRandMask1, gRandMask2;
s32 sGpRaceResultsState, gTotalLapCount, sPlayerResultsTimer[4];
s8 gTitleDemoState, gGamePaused;
Racer gRacers[30];
Camera gCameras[4];
void Math_Rand1Init(s32 seed, s32 mask) { (void)seed; (void)mask; }
void Math_Rand2Init(s32 seed, s32 mask) { (void)seed; (void)mask; }
#include "port/3ds/game/gdx3ds_benchmark_state.c"
static unsigned endpoint(void) {
    unsigned out[20]; gdx3ds_replay_state(out); return out[19];
}
int main(void) {
    unsigned running[20], paused[20];
    gGameMode = GAMEMODE_GP_RACE; gTotalRacers = 30;
    gTotalLapCount = 3; gTitleDemoState = TITLE_DEMO_INACTIVE;
    gRacers[0].stateFlags = RACER_STATE_FINISHED;
    gRacers[0].lap = 4; gRacers[0].lapsCompleted = 4;
    gRacers[0].raceTime = 98192; gRacers[0].position = 1;
    sGpRaceResultsState = GP_RESULTS_TOP_6_TIMING;
    sPlayerResultsTimer[0] = 600;
    assert(endpoint() == 0);
    sGpRaceResultsState = GP_RESULTS_RACE_RESULT;
    sPlayerResultsTimer[0] = 29; assert(endpoint() == 0);
    sPlayerResultsTimer[0] = 30; assert(endpoint() == 1);
    gTitleDemoState = TITLE_DEMO_ACTIVE; assert(endpoint() == 0);
    gTitleDemoState = TITLE_DEMO_INACTIVE;
    gTotalLapCount = 1; assert(endpoint() == 0); gTotalLapCount = 3;
    gRacers[0].stateFlags = 0; assert(endpoint() == 0);
    gRacers[0].stateFlags = RACER_STATE_FINISHED;
    gRacers[0].lapsCompleted = 3; assert(endpoint() == 0);
    gRacers[0].lapsCompleted = 4;
    gRacers[0].raceTime = 0; assert(endpoint() == 0);
    gRacers[0].raceTime = 98192;
    gGameMode = GAMEMODE_TIME_ATTACK; assert(endpoint() == 0);
    gGameMode = GAMEMODE_GP_RACE;
    sGpRaceResultsState = GP_RESULTS_TOTAL_RANKING; assert(endpoint() == 0);
    gGamePaused = 0; gdx3ds_replay_state(running);
    gGamePaused = 1; gdx3ds_replay_state(paused);
    assert(running[13] != paused[13]);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'endpoint.c'
            binary = Path(tmp) / 'endpoint'
            source.write_text(harness)
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fno-builtin',
                            '-fsanitize=undefined', '-I', str(ROOT),
                            '-I', str(decomp), '-I', str(decomp / 'include'),
                            '-DPORT=1', '-DGDIFFUSER_PORT=1', '-DF3DEX_GBI_2=1',
                            '-D_LANGUAGE_C=1', '-DVERSION_US=1',
                            str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
