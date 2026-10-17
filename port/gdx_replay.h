/* M0.5 diagnostic stream. All disk I/O is in open/service/close, never poll. */
#pragma once
#include <stdint.h>
#include "gdx_input_script.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GDX_REPLAY_WORDS 20
#define GDX_REPLAY_RECORD_BYTES 101
/* mode: 1 record, 2 playback. identity: 64 lowercase SHA256 hex bytes. */
int gdx_replay_open(int mode, const char* input, const char* output, const char* identity);
int gdx_replay_service(void);
/* 1 consumed, 0 endpoint, -1 error. Four controllers, semantic state BEFORE this poll. */
int gdx_replay_poll(GdxInputPad pads[4], unsigned char present[4], const unsigned int state[20]);
int gdx_replay_close(int complete);
const char* gdx_replay_error(void);
#ifdef __cplusplus
}
#endif
