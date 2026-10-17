#include "texture_pack.h"
#include <string.h>
static uint32_t u32(const unsigned char* b) {
    return (uint32_t)b[0]|(uint32_t)b[1]<<8|(uint32_t)b[2]<<16|(uint32_t)b[3]<<24;
}
static int hash_matches(const unsigned char* bytes,const char* hex) {
    static const char digits[]="0123456789abcdef";
    for(unsigned i=0;i<32;i++)
        if(hex[2*i]!=digits[bytes[i]>>4] || hex[2*i+1]!=digits[bytes[i]&15]) return 0;
    return 1;
}
static uint32_t crc32(const unsigned char* b,size_t size) {
    uint32_t crc=~0u;
    for(size_t i=0;i<size;i++) {
        crc^=(i>=28 && i<32)?0:b[i];
        for(unsigned bit=0;bit<8;bit++) crc=(crc>>1)^(0xedb88320u & (0u-(crc&1u)));
    }
    return ~crc;
}
const char* swatch_pack_validate(const void* bytes,size_t size,SwatchPack* out) {
    if(!out) return "null output";
    memset(out,0,sizeof(*out));
    if(!bytes || size!=SWATCH_PACK_BYTES) return "size";
    const unsigned char* b=bytes;
    if(memcmp(b,"GDXSWCH\0",8) || u32(b+8)!=1 || u32(b+12)!=size ||
       u32(b+16)!=8 || u32(b+20)!=128 || u32(b+24)!=512) return "header";
    if(!hash_matches(b+32,"f654cebe506385d9bb3ce8664cbf6dcd96593c6600f3e8486c31a019b3a96934") ||
       !hash_matches(b+64,"e5845153f9dbca29d7fff4890e455fa90173438070d1db074186cd2a75fae334")) return "identity";
    for(unsigned i=96;i<128;i++) if(b[i]) return "reserved";
    uint32_t crc=u32(b+28);
    if(crc32(b,size)!=crc) return "CRC";
    static const uint32_t widths[8]={16,16,16,16,64,16,32,32};
    static const uint32_t heights[8]={16,16,16,16,16,32,32,32};
    static const uint32_t formats[8]={1,3,2,1,1,1,1,1};
    static const uint32_t masks[8][2]={{4,4},{4,4},{4,4},{4,4},{6,4},{4,5},{5,5},{5,5}};
    SwatchPack result={0};result.crc=crc;
    uint32_t offset=512;
    for(unsigned i=0;i<8;i++) {
        const unsigned char* e=b+128+i*48;
        uint32_t length=widths[i]*heights[i]*4;
        uint32_t mode_t=(i==1 || i==2 || i==7)?0:1;
        if(u32(e)!=i || u32(e+4)!=widths[i] || u32(e+8)!=heights[i] ||
           u32(e+12)!=formats[i] || u32(e+16)!=offset || u32(e+20)!=length ||
           u32(e+24)!=1 || u32(e+28)!=mode_t || u32(e+32)!=masks[i][0] ||
           u32(e+36)!=masks[i][1] || u32(e+40)!=0 || u32(e+44)!=0) return "tile catalog/range";
        if(offset>size || length>size-offset) return "pixel bounds";
        result.tiles[i]=(SwatchTexture){widths[i],heights[i],formats[i],1,mode_t,masks[i][0],masks[i][1],b+offset,length};
        offset+=length;
    }
    if(offset!=size) return "trailing payload";
    *out=result;
    return NULL;
}
