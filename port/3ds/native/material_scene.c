#include "material_scene.h"
#include <string.h>
const char* material_scene_prepare(const NativeMaterial* source,unsigned count,NativeMaterial out[8]) {
    if(!out) return "null scene output";
    memset(out,0,8*sizeof(*out));
    if(!source || count!=8) return "unsupported scene material count";
    static const NativeMaterial expected[8]={
        {0,12,1,0xffffffff,0xffa5630e,0,1,0},
        {12,42,2,0xff00ffff,0xffa5630e,1,1,0},
        {54,6,3,0xff00ffff,0xffa5630e,1,1,0},
        {60,6,4,0xffffffff,0xffa5630e,1,1,0},
        {66,156,5,0xffffffff,0xffa5630e,1,1,0},
        {222,12,6,0xffffffff,0xff000000,1,1,0},
        {234,24,7,0xffffffff,0xff000000,1,1,0},
        {258,30,0,0xffffeed1,0xffa5630e,1,1,0}
    };
    for(unsigned i=0;i<8;i++)
        if(memcmp(source+i,expected+i,sizeof(*source))) return "unsupported source material recipe/range";
    memcpy(out,source,8*sizeof(*out));
    for(unsigned i=0;i<5;i++) out[i].env=0xffff0000; // little-endian RGBA stock (0,0,255,255)
    return NULL;
}
