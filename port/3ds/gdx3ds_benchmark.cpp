/* M0 diagnostic build only. Link wrapping leaves the production game unchanged.
 * Timers are elapsed ticks, including preemption/fiber yields, not thread CPU time.
 * Capture in fixed storage; CSV I/O happens only after capture has stopped. */
#include <3ds.h>
#include <malloc.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "gdx3ds_config.h"

extern "C" {
void __real_func_800690FC(void);
void* __real_func_80069698(void* gfx);
void __real_gdx_gfx_run(void* dl, size_t bytes, int ucode);
void __real_gdx_vi_present_fallback(void);
void __real_Race_Init(void);
void gdx3ds_benchmark_race_seed(void);
void gdx3ds_benchmark_state(unsigned int out[11]);
void gdx_request_quit(void);
void gdx3ds_gpuprof_set_external_pacing(int on);
extern u32 __ctru_heap_size, __ctru_linear_heap_size;
}

namespace {
constexpr unsigned kCapacity = 8192;
struct Sample {
    uint64_t update, draw, gfx;
    unsigned int state[11];
    unsigned int tasks;
};
Sample sSamples[kCapacity];
unsigned sCount, sLimit;
int sMode;
uint64_t sUpdate;
bool sFinished;
bool sRaceOnly;
constexpr char kOutput[] = "sdmc:/3ds/gdiffuser/benchmark.csv";

void Receipt(const char* message) {
    svcOutputDebugString(message, std::strlen(message));
}

void MemoryReceipt(const char* phase) {
    Handle limit = 0;
    s64 maxCommit = -1, currentCommit = -1;
    ResourceLimitType type = RESLIMIT_COMMIT;
    if (R_SUCCEEDED(svcGetResourceLimit(&limit, CUR_PROCESS_HANDLE))) {
        svcGetResourceLimitLimitValues(&maxCommit, limit, &type, 1);
        svcGetResourceLimitCurrentValues(&currentCommit, limit, &type, 1);
        svcCloseHandle(limit);
    }
    const auto mi = mallinfo();
    char message[320];
    std::snprintf(message, sizeof(message),
        "[m0-memory] phase=%s limit=%lld commit=%lld heapCapacity=%lu heapUsed=%lu "
        "heapFree=%lu linearCapacity=%lu linearFree=%lu captureBytes=%lu",
        phase, (long long)maxCommit, (long long)currentCommit,
        (unsigned long)__ctru_heap_size, (unsigned long)mi.uordblks,
        (unsigned long)mi.fordblks, (unsigned long)__ctru_linear_heap_size,
        (unsigned long)linearSpaceFree(), (unsigned long)sizeof(sSamples));
    Receipt(message);
}
}

extern "C" void gdx3ds_benchmark_init(void) {
    sMode = gdx3ds_config_get_int("benchmark", "mode", 0);
    if (sMode < 1 || sMode > 2) { sMode = 0; return; }
    int limit = gdx3ds_config_get_int("benchmark", "frames", 3000);
    sLimit = (unsigned)(limit < 64 ? 64 : limit > (int)kCapacity ? kCapacity : limit);
    sRaceOnly = gdx3ds_config_get_bool("benchmark", "race_only", 0) != 0;
    // Both A/B paths use the sequential scheduler. Preserve game Draw side effects.
    gdx3ds_config_set_int("debug", "renderthread", 0);
    gdx3ds_config_set_int("perf", "rival_detail", 0);
    gdx3ds_config_set_int("perf", "rival_detail_auto", 0);
    gdx3ds_config_set_int("stereo", "enabled", 0);
    // A bypassed task never reaches the renderer's vblank wait. Give BOTH paths
    // one explicit host-loop vblank, disabling the renderer's duplicate wait.
    gdx3ds_gpuprof_set_external_pacing(1);
    setenv("GDX_RAND_SEED1", "12345", 1);
    setenv("GDX_RAND_SEED2", "67890", 1);
    setenv("GDX_INPUT_SCRIPT", "sdmc:/3ds/gdiffuser/benchmark-input.txt", 1);
    Receipt(sMode == 1 ? "[m0] mode=render seed1=12345 seed2=67890"
                       : "[m0] mode=bypass seed1=12345 seed2=67890");
    MemoryReceipt("pre-gfx");
}

extern "C" void gdx3ds_benchmark_pace(void) {
    if (sMode) gspWaitForVBlank();
}

extern "C" void __wrap_Race_Init(void) {
    if (sMode && sRaceOnly) gdx3ds_benchmark_race_seed();
    __real_Race_Init();
}

extern "C" void __wrap_func_800690FC(void) {
    if (!sMode) { __real_func_800690FC(); return; }
    const auto start = svcGetSystemTick();
    __real_func_800690FC();
    sUpdate = svcGetSystemTick() - start;
}

extern "C" void* __wrap_func_80069698(void* gfx) {
    if (!sMode) return __real_func_80069698(gfx);
    const auto start = svcGetSystemTick();
    void* result = __real_func_80069698(gfx);
    const auto elapsed = svcGetSystemTick() - start;
    unsigned int state[11];
    gdx3ds_benchmark_state(state);
    if (sRaceOnly && ((state[1] & 31) != 1 || state[3] != 30)) return result;
    if (sCount < sLimit) {
        Sample& sample = sSamples[sCount++];
        sample.update = sUpdate;
        sample.draw = elapsed;
        std::memcpy(sample.state, state, sizeof(state));
        if (sCount == sLimit) gdx_request_quit();
    }
    return result;
}

extern "C" void __wrap_gdx_gfx_run(void* dl, size_t bytes, int ucode) {
    if (!sMode) { __real_gdx_gfx_run(dl, bytes, ucode); return; }
    const auto start = svcGetSystemTick();
    if (sMode == 1) __real_gdx_gfx_run(dl, bytes, ucode);
    if (sCount > 0 && sCount <= sLimit) {
        sSamples[sCount - 1].gfx += svcGetSystemTick() - start;
        ++sSamples[sCount - 1].tasks;
    }
}

extern "C" void __wrap_gdx_vi_present_fallback(void) {
    if (sMode != 2) __real_gdx_vi_present_fallback();
}

extern "C" void gdx3ds_benchmark_finish(void) {
    if (!sMode || sFinished) return;
    sFinished = true;
    MemoryReceipt("end");
    constexpr char temporary[] = "sdmc:/3ds/gdiffuser/benchmark.csv.tmp";
    FILE* output = std::fopen(temporary, "w");
    if (!output) { Receipt("[m0] ERROR opening benchmark.csv"); return; }
    bool ok = std::fprintf(output, "# mode=%s seed1=12345 seed2=67890 samples=%u race_only=%d\n"
        "tick,mode,course,racers,state_hash,rng_hash,position_hash,velocity_hash,"
        "status_hash,race_clock_hash,vi_tick,update_us,draw_us,gfx_us,tasks\n",
        sMode == 1 ? "render" : "bypass", sCount, sRaceOnly ? 1 : 0) > 0;
    const double toUs = 1000.0 / CPU_TICKS_PER_MSEC;
    for (unsigned i = 0; i < sCount; ++i) {
        const Sample& s = sSamples[i];
        if (std::fprintf(output, "%u,%u,%u,%u,%08x,%08x,%08x,%08x,%08x,%08x,%u,%.3f,%.3f,%.3f,%u\n",
            s.state[0], s.state[1], s.state[2], s.state[3], s.state[4], s.state[5],
            s.state[6], s.state[7], s.state[8], s.state[9], s.state[10],
            s.update * toUs, s.draw * toUs, s.gfx * toUs, s.tasks) < 0) ok = false;
    }
    const auto mi = mallinfo();
    if (std::fprintf(output, "# heapCapacity=%lu heapUsed=%lu heapFree=%lu "
        "linearCapacity=%lu linearFree=%lu captureBytes=%lu\n",
        (unsigned long)__ctru_heap_size, (unsigned long)mi.uordblks,
        (unsigned long)mi.fordblks, (unsigned long)__ctru_linear_heap_size,
        (unsigned long)linearSpaceFree(), (unsigned long)sizeof(sSamples)) < 0) ok = false;
    if (std::fclose(output) != 0) ok = false;
    if (ok && std::rename(temporary, kOutput) != 0) ok = false;
    Receipt(ok ? "[m0] capture saved" : "[m0] ERROR writing capture");
}
