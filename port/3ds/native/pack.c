#include "pack.h"
#include <math.h>
#include <string.h>
_Static_assert(sizeof(NativeVertex)==36,"vertex ABI");
_Static_assert(sizeof(NativeMaterial)==32,"material ABI");
static uint32_t word(const uint8_t* p) { return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24; }
static uint32_t checksum(const uint8_t* p,size_t n) {
    uint32_t crc=~0u;
    for(size_t i=0;i<n;i++) {
        crc ^= i>=40 && i<44 ? 0 : p[i];
        for(int j=0;j<8;j++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1)));
    }
    return ~crc;
}
const char* native_pack_validate(const void* bytes,size_t size,NativeMesh* out) {
    memset(out,0,sizeof(*out));
    const uint8_t* p=bytes;
    const uint16_t endian=1;
    if(!p || size<192 || size>NATIVE_PACK_MAX || ((uintptr_t)p&3) || *(const uint8_t*)&endian!=1) return "size/alignment/endian";
    if(memcmp(p,"GDXM1A\0\0",8) || word(p+8)!=1 || word(p+12)!=size || word(p+44)!=1 || word(p+188)) return "header/version";
    uint32_t nv=word(p+16),ni=word(p+20),nm=word(p+24),vo=word(p+28),io=word(p+32),mo=word(p+36);
    if(!nv || nv>4096 || !ni || ni>24576 || ni%3 || !nm || nm>64) return "counts/budget";
    if(vo!=192 || io!=vo+nv*36 || mo!=((io+ni*2+3)&~3u) || (mo&3) || size!=mo+nm*32) return "sections";
    for(uint32_t i=io+ni*2;i<mo;i++) if(p[i]) return "section padding";
    if(word(p+40)!=checksum(p,size)) return "checksum";
    NativeMesh m={nv,ni,nm,word(p+40),(const NativeVertex*)(p+vo),(const uint16_t*)(p+io),(const NativeMaterial*)(p+mo),{0}};
    memcpy(m.bounds,p+164,24);
    for(int j=0;j<6;j++) if(!isfinite(m.bounds[j])) return "nonfinite bounds";
    for(int j=0;j<3;j++) if(m.bounds[j]>m.bounds[j+3]) return "bounds order";
    for(uint32_t i=0;i<nv;i++) {
        const NativeVertex* v=m.vertices+i;
        for(int j=0;j<3;j++) if(!isfinite(v->position[j]) || v->position[j]<m.bounds[j] || v->position[j]>m.bounds[j+3]) return "vertex bounds";
        for(int j=0;j<4;j++) if(!isfinite(v->color[j]) || v->color[j]<0 || v->color[j]>1) return "vertex color";
    }
    for(uint32_t i=0;i<ni;i++) if(m.indices[i]>=nv) return "index reference";
    uint32_t next=0;
    for(uint32_t i=0;i<nm;i++) {
        const NativeMaterial* mat=m.materials+i;
        if(mat->first!=next || !mat->count || mat->count%3 || mat->count>ni-next || mat->tile>7 || mat->combine>1 || mat->flags!=1 || mat->reserved) return "material range/state";
        next+=mat->count;
    }
    if(next!=ni) return "material coverage";
    *out=m;
    return NULL;
}
