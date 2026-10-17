#ifndef GDX_NATIVE_PACK_H
#define GDX_NATIVE_PACK_H
#include <stddef.h>
#include <stdint.h>
#define NATIVE_PACK_MAX (1024u*1024u)
typedef struct { float position[3], color[4]; uint8_t normal_alpha[4]; int16_t uv[2]; } NativeVertex;
typedef struct { uint32_t first,count,tile,prim,env,combine,flags,reserved; } NativeMaterial;
typedef struct {
    uint32_t vertex_count,index_count,material_count,crc;
    const NativeVertex* vertices;
    const uint16_t* indices;
    const NativeMaterial* materials;
    float bounds[6];
} NativeMesh;
/* Borrowed views: caller retains aligned little-endian input until upload completes.
   No allocation, no I/O; on error out is zeroed. */
const char* native_pack_validate(const void* bytes,size_t size,NativeMesh* out);
#endif
