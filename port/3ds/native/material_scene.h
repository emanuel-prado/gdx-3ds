#ifndef GDX_MATERIAL_SCENE_H
#define GDX_MATERIAL_SCENE_H
#include "pack.h"
#define MATERIAL_SCENE_ID "blue-falcon-textured-unlit-v1"
/* Explicit new scene semantics: ignores M1a's approximation vertex colors.
   Retains original source material records, stock initial livery, SHADE=1,q=0.
   Does not redefine the v1 mesh pack approximation flag as accurate materials. */
const char* material_scene_prepare(const NativeMaterial* source,unsigned count,NativeMaterial out[8]);
#endif
