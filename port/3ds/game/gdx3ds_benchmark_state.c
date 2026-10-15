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
