#include "gdx_replay.h"
#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <limits.h>
#if UINT_MAX != 0xffffffffu
#error Replay semantic words require 32-bit unsigned int
#endif

/* Wire encoding is explicitly little endian, without ABI padding. One pending
 * record: the host loop services it before the next poll. Overflow fails closed. */
static FILE *src, *dst;
static int active, pending, ready, endpoint, failed;
static unsigned char queued[101], next[101];
static uint64_t count;
static uint32_t checksum, outputChecksum;
static const char* error;
static void put32(unsigned char* p, uint32_t v) {
    int i; for (i=0;i<4;i++) p[i]=(unsigned char)(v>>(8*i));
}
static uint32_t get32(const unsigned char* p) {
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static uint32_t hash(uint32_t h, const unsigned char* p, unsigned n) {
    unsigned i; for(i=0;i<n;i++) h=(h^p[i])*16777619u; return h;
}
static int fail(const char* why) { failed=1; error=why; return -1; }
const char* gdx_replay_error(void) { return error ? error : "none"; }

int gdx_replay_open(int mode, const char* input, const char* output, const char* identity) {
    unsigned char header[72]; unsigned i;
    if (src || dst) return fail("session already open");
    active=mode; pending=ready=endpoint=failed=0; count=0; checksum=outputChecksum=2166136261u; error=0;
    if ((mode!=1 && mode!=2) || !output || (mode==2 && (!input || !strcmp(input,output))) ||
        !identity || strlen(identity)!=64)
        return fail("invalid mode/identity");
    for(i=0;i<64;i++) if (!isdigit((unsigned char)identity[i]) &&
        !(identity[i]>='a' && identity[i]<='f')) return fail("invalid identity");
    memcpy(header,"GDXRPL\1\0",8); memcpy(header+8,identity,64);
    if (mode==2) {
        unsigned char actual[72];
        src=fopen(input,"rb");
        if(!src) return fail("cannot open replay");
        if(fread(actual,1,72,src)!=72 || memcmp(header,actual,72))
            return fail("replay version/configuration identity mismatch");
    }
    dst=fopen(output,"wb");
    if(!dst || fwrite(header,1,72,dst)!=72) return fail("cannot create output");
    return 1;
}
int gdx_replay_service(void) {
    if(failed) return -1;
    if(pending) {
        if(fwrite(queued,1,101,dst)!=101) return fail("write failed");
        outputChecksum=hash(outputChecksum,queued,101);
        pending=0;
    }
    if(active==2 && !ready && !endpoint) {
        int type=fgetc(src);
        if(type==1) {
            unsigned i;
            next[0]=1;
            if(fread(next+1,1,100,src)!=100) return fail("truncated poll");
            for(i=0;i<4;i++) if(next[5+5*i]>1) return fail("invalid controller presence");
            if(get32(next+81)>1 || get32(next+97)>1) return fail("invalid state boolean");
            ready=1;
        } else if(type==2) {
            unsigned char footer[13]; uint64_t recorded;
            if(fread(footer,1,13,src)!=13) return fail("truncated footer");
            recorded=get32(footer)|((uint64_t)get32(footer+4)<<32);
            if(recorded!=count || get32(footer+8)!=checksum || footer[12]!=1 ||
                fgetc(src)!=EOF || ferror(src)) return fail("incomplete/corrupt endpoint");
            endpoint=1;
        } else return fail("missing footer or invalid record");
    }
    return 1;
}
int gdx_replay_poll(GdxInputPad pads[4], unsigned char present[4], const unsigned int state[20]) {
    unsigned i;
    if(failed) return -1;
    if(pending) return fail("unserviced input buffer");
    if(active==2) {
        if(endpoint) return 0;
        if(!ready) return fail("replay was not prefetched");
        for(i=0;i<4;i++) {
            const unsigned char* p=next+1+5*i;
            pads[i].buttons=(unsigned short)(p[0]|(p[1]<<8));
            pads[i].stickX=(signed char)p[2]; pads[i].stickY=(signed char)p[3]; present[i]=p[4];
        }
        ready=0;
    }
    queued[0]=1;
    for(i=0;i<4;i++) {
        unsigned char* p=queued+1+5*i;
        if(present[i]>1) return fail("invalid controller presence");
        p[0]=(unsigned char)pads[i].buttons; p[1]=(unsigned char)(pads[i].buttons>>8);
        p[2]=(unsigned char)pads[i].stickX; p[3]=(unsigned char)pads[i].stickY; p[4]=present[i];
    }
    for(i=0;i<20;i++) put32(queued+21+4*i,state[i]);
    /* Input checksum validates the source; output has its own semantic checksum. */
    checksum=hash(checksum,active==2?next:queued,101);
    count++; pending=1; return 1;
}
int gdx_replay_close(int complete) {
    unsigned char footer[14]; int ok=!failed;
    if(ok && gdx_replay_service()<0) ok=0;
    if(dst && ok) {
        footer[0]=2; put32(footer+1,(uint32_t)count); put32(footer+5,(uint32_t)(count>>32));
        put32(footer+9,outputChecksum); footer[13]=(unsigned char)(complete && (active==1 || endpoint));
        if(fwrite(footer,1,14,dst)!=14) ok=0;
    }
    if(src) { fclose(src); src=0; }
    if(dst) { if(fclose(dst)) ok=0; dst=0; }
    active=0;
    if (!ok && !failed) fail("session close failed");
    return ok ? 1 : -1;
}
