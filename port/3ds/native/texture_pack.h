#ifndef GDX_TEXTURE_PACK_H
#define GDX_TEXTURE_PACK_H
#include <stddef.h>
#include <stdint.h>
#define SWATCH_PACK_BYTES 18944u
#define SWATCH_TEXTURE_COUNT 8u
typedef struct {
    uint32_t width,height,source_format,mode_s,mode_t,mask_s,mask_t;
    const unsigned char* pixels;
    size_t bytes;
} SwatchTexture;
typedef struct { uint32_t crc; SwatchTexture tiles[SWATCH_TEXTURE_COUNT]; } SwatchPack;
/* No allocation or GPU access; zeroes output on failure. Borrows input pixels. */
const char* swatch_pack_validate(const void* bytes,size_t size,SwatchPack* out);
#endif
