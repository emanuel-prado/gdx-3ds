/* Selected semantic state only; no pointers, padding, model matrices or graphics LOD.
 * Compiled with the real game's struct definitions, avoiding ABI guesses in C++. */
#include "global.h"
#include "fzx_racer.h"

extern s32 gGameMode, gTotalRacers, gCourseIndex;
extern u32 gGameFrameCount;
extern s32 gRandSeed1, gRandSeed2;
extern u32 gRandMask1, gRandMask2;
extern s32 D_800CCFB0;

void gdx3ds_benchmark_race_seed(void) {
    /* Explicit test initial state, shared by render/bypass; not production behavior. */
    Math_Rand1Init(12345, 24690);
    Math_Rand2Init(135780, 67890);
    gGameFrameCount = 0;
}

static u32 HashWord(u32 h, u32 word) {
    return (h ^ word) * 16777619u;
}

static u32 FloatBits(f32 value) {
    union { f32 f; u32 u; } bits;
    bits.f = value;
    return bits.u;
}

void gdx3ds_benchmark_state(unsigned int out[11]) {
    u32 state = 2166136261u;
    u32 position = 2166136261u, velocity = 2166136261u;
    u32 status = 2166136261u, clock = 2166136261u;
    u32 rng = HashWord(HashWord(HashWord(HashWord(2166136261u,
        (u32)gRandSeed1), gRandMask1), (u32)gRandSeed2), gRandMask2);
    int count = gTotalRacers;
    int i;
    if (count < 0) count = 0;
    if (count > TOTAL_RACER_COUNT) count = TOTAL_RACER_COUNT;
    for (i = 0; i < count; ++i) {
        const Racer* r = &gRacers[i];
        state = HashWord(state, (u32)r->id);
        state = HashWord(state, (u32)r->stateFlags);
        state = HashWord(state, FloatBits(r->segmentPositionInfo.segmentTValue));
        state = HashWord(state, FloatBits(r->segmentPositionInfo.pos.x));
        state = HashWord(state, FloatBits(r->segmentPositionInfo.pos.y));
        state = HashWord(state, FloatBits(r->segmentPositionInfo.pos.z));
        state = HashWord(state, FloatBits(r->velocity.x));
        state = HashWord(state, FloatBits(r->velocity.y));
        state = HashWord(state, FloatBits(r->velocity.z));
        state = HashWord(state, FloatBits(r->speed));
        state = HashWord(state, (u32)r->raceTime);
        state = HashWord(state, (u32)r->lap);
        state = HashWord(state, (u32)r->position);
        position = HashWord(position, FloatBits(r->segmentPositionInfo.segmentTValue));
        position = HashWord(position, FloatBits(r->segmentPositionInfo.pos.x));
        position = HashWord(position, FloatBits(r->segmentPositionInfo.pos.y));
        position = HashWord(position, FloatBits(r->segmentPositionInfo.pos.z));
        velocity = HashWord(velocity, FloatBits(r->velocity.x));
        velocity = HashWord(velocity, FloatBits(r->velocity.y));
        velocity = HashWord(velocity, FloatBits(r->velocity.z));
        velocity = HashWord(velocity, FloatBits(r->speed));
        status = HashWord(status, (u32)r->id);
        status = HashWord(status, (u32)r->stateFlags);
        status = HashWord(status, (u32)r->lap);
        status = HashWord(status, (u32)r->position);
        clock = HashWord(clock, (u32)r->raceTime);
    }
    out[0] = gGameFrameCount;
    out[1] = (u32)gGameMode;
    out[2] = (u32)gCourseIndex;
    out[3] = (u32)count;
    out[4] = state;
    out[5] = rng;
    out[6] = position;
    out[7] = velocity;
    out[8] = status;
    out[9] = clock;
    out[10] = (u32)D_800CCFB0;
}

/* Full-session oracle: no raw struct hashing, pointers, padding or matrices. */
#include "fzx_camera.h"
extern Camera gCameras[];
extern s32 sGpRaceResultsState, gTitleDemoState, gTotalLapCount, gGamePaused;
extern s32 sPlayerResultsTimer[4];
void gdx3ds_replay_state(unsigned int out[20]) {
    u32 energy = 2166136261u, lod = 2166136261u, camera = 2166136261u;
    int i;
    gdx3ds_benchmark_state(out);
    for (i = 0; i < (int)out[3]; ++i) {
        const Racer* r = &gRacers[i];
        energy = HashWord(energy, FloatBits(r->energy));
        energy = HashWord(energy, FloatBits(r->maxEnergy));
        energy = HashWord(energy, (u32)r->attackState);
        energy = HashWord(energy, (u32)r->boostTimer);
        energy = HashWord(energy, (u32)r->spinOutTimer);
        energy = HashWord(energy, FloatBits(r->raceDistance));
        energy = HashWord(energy, (u32)r->lapsCompleted);
        energy = HashWord(energy, (u32)r->lapTimes[0]);
        energy = HashWord(energy, (u32)r->lapTimes[1]);
        energy = HashWord(energy, (u32)r->lapTimes[2]);
        lod = HashWord(lod, (u32)r->machineLod);
    }
    for (i = 0; i < 4; ++i) {
        const Camera* c = &gCameras[i];
        camera = HashWord(camera, (u32)c->mode);
        camera = HashWord(camera, (u32)c->state);
        camera = HashWord(camera, FloatBits(c->eye.x));
        camera = HashWord(camera, FloatBits(c->eye.y));
        camera = HashWord(camera, FloatBits(c->eye.z));
        camera = HashWord(camera, FloatBits(c->at.x));
        camera = HashWord(camera, FloatBits(c->at.y));
        camera = HashWord(camera, FloatBits(c->at.z));
        camera = HashWord(camera, FloatBits(c->fov));
    }
    camera = HashWord(camera, (u32)gGamePaused);
    out[11] = energy; out[12] = lod; out[13] = camera;
    out[14] = (u32)gRacers[0].lap;
    out[15] = (gRacers[0].stateFlags & RACER_STATE_FINISHED) != 0;
    out[16] = (u32)gRacers[0].position;
    out[17] = (u32)gRacers[0].raceTime;
    out[18] = (u32)gRacers[0].lapsCompleted;
    /* The ranking screen has actually been reached, rather than just a finish flag.
     * Reject demos, forced-finish races and non-three-lap modes. */
    out[19] = (gGameMode & 31) == 1 && gTitleDemoState == 0 && gTotalLapCount == 3 &&
        out[15] && out[18] == 4 && out[17] > 0 &&
        sGpRaceResultsState == 1 && sPlayerResultsTimer[0] >= 30;
}
