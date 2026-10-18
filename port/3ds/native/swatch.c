#include <3ds.h>
#include <citro3d.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "swatch_shader_shbin.h"
#include "texture_pack.h"
#define DIR "sdmc:/3ds/gdiffuser-native-swatch/"
#define FRAMES 120u
#define TRANSFER (GX_TRANSFER_FLIP_VERT(0)|GX_TRANSFER_OUT_TILED(0)|GX_TRANSFER_RAW_COPY(0)|GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8)|GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8)|GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO))
typedef struct { float x,y,z,u,v; } Vertex;
static void quad(Vertex* v,float x,float y,float w,float h) {
    const Vertex q[6]={{x,y,0,0,0},{x,y-h,0,0,1},{x+w,y,0,1,0},
                       {x+w,y,0,1,0},{x,y-h,0,0,1},{x+w,y-h,0,1,1}};
    memcpy(v,q,sizeof(q));
}
static void put32(unsigned char* b,unsigned v) { for(unsigned i=0;i<4;i++) b[i]=(unsigned char)(v>>(8*i)); }
static int capture(void) {
    FILE* f=fopen(DIR "swatches.bmp","wb");if(!f) return 0;
    unsigned char header[54]={0},row[1200];header[0]='B';header[1]='M';
    put32(header+2,54+400*240*3);put32(header+10,54);put32(header+14,40);
    put32(header+18,400);put32(header+22,240);header[26]=1;header[28]=24;
    int ok=fwrite(header,1,54,f)==54;u8* fb=gfxGetFramebuffer(GFX_TOP,GFX_LEFT,NULL,NULL);
    for(int y=239;y>=0;y--) {
        for(int x=0;x<400;x++) memcpy(row+3*x,fb+3*(x*240+239-y),3);
        if(fwrite(row,1,sizeof(row),f)!=sizeof(row)) ok=0;
    }
    if(fclose(f)) ok=0;
    return ok;
}
int main(void) {
    gfxInitDefault();gfxSet3D(false);consoleInit(GFX_BOTTOM,NULL);osSetSpeedupEnable(false);
    mkdir("sdmc:/3ds",0777);mkdir(DIR,0777);
    printf("Native texture upload diagnostic\n%s\nTiles 0..3 top, 4..7 middle\nBottom marker TL red / TR green\nBL blue / BR white\n120 frames; START abort\n",NATIVE_BUILD_ID);
    int status=1;FILE* log=fopen(DIR "run.log","w");FILE* input=NULL;
    unsigned char* bytes=NULL;Vertex* vb=NULL;C3D_Tex textures[9]={0};unsigned allocated=0;
    bool c3d=false,program_ready=false;DVLB_s* dvlb=NULL;shaderProgram_s program={0};
    SwatchPack pack={0};unsigned completed=0;bool new3ds=false;APT_CheckNew3DS(&new3ds);
    if(!log) goto done;
    fprintf(log,"build=%s\nsource=%s\ntoolchain=%s\nmodel_new3ds=%d speedup_requested=0 stereo=0\n",NATIVE_BUILD_ID,NATIVE_SOURCE_ID,NATIVE_TOOLCHAIN_ID,new3ds);
    input=fopen(DIR "textures.gdns","rb");
    if(!input || fseek(input,0,SEEK_END) || ftell(input)!=(long)SWATCH_PACK_BYTES || fseek(input,0,SEEK_SET)) {
        fprintf(log,"ERROR input size/open\n");goto done;
    }
    bytes=malloc(SWATCH_PACK_BYTES);
    if(!bytes || fread(bytes,1,SWATCH_PACK_BYTES,input)!=SWATCH_PACK_BYTES) { fprintf(log,"ERROR input read\n");goto done; }
    fclose(input);input=NULL;
    const char* error=swatch_pack_validate(bytes,SWATCH_PACK_BYTES,&pack);
    if(error) { fprintf(log,"ERROR validation %s\n",error);goto done; }
    fprintf(log,"validated_crc32=%08lx pack_bytes=%u gpu_content_bytes=18432\n",(unsigned long)pack.crc,SWATCH_PACK_BYTES);
    u32 before=linearSpaceFree();
    c3d=C3D_Init(64*1024);if(!c3d) { fprintf(log,"ERROR C3D init\n");goto done; }
    C3D_RenderTarget* target=C3D_RenderTargetCreate(240,400,GPU_RB_RGBA8,GPU_RB_DEPTH24_STENCIL8);
    if(!target) { fprintf(log,"ERROR target\n");goto done; }
    C3D_RenderTargetSetOutput(target,GFX_TOP,GFX_LEFT,TRANSFER);
    dvlb=DVLB_ParseFile((u32*)swatch_shader_shbin,swatch_shader_shbin_size);
    if(!dvlb || shaderProgramInit(&program)<0) { fprintf(log,"ERROR shader\n");goto done; }
    program_ready=true;
    if(shaderProgramSetVsh(&program,&dvlb->DVLE[0])<0) { fprintf(log,"ERROR shader bind\n");goto done; }
    C3D_BindProgram(&program);
    int projection=shaderInstanceGetUniformLocation(program.vertexShader,"projection");
    if(projection<0) { fprintf(log,"ERROR uniform\n");goto done; }
    C3D_Mtx matrix;Mtx_OrthoTilt(&matrix,0,400,0,240,-1,1,false);
    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,projection,&matrix);
    vb=linearAlloc(9*6*sizeof(*vb));if(!vb) { fprintf(log,"ERROR vertex buffer\n");goto done; }
    for(unsigned i=0;i<9;i++) {
        unsigned width=i<8?pack.tiles[i].width:8,height=i<8?pack.tiles[i].height:8;
        if(!C3D_TexInit(&textures[i],width,height,GPU_RGBA8)) { fprintf(log,"ERROR texture %u\n",i);goto done; }
        allocated++;
        C3D_TexSetFilter(&textures[i],GPU_NEAREST,GPU_NEAREST);
        C3D_TexSetWrap(&textures[i],GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE);
        if(i<8) {
            memcpy(textures[i].data,pack.tiles[i].pixels,pack.tiles[i].bytes);
            float scale=64.0f/height;if(width*scale>80) scale=80.0f/width;
            quad(vb+6*i,8+(i%4)*98,232-(i/4)*84,width*scale,height*scale);
        } else {
            // Four asymmetric color quadrants, same bottom-up Morton/ABGR convention.
            static const u32 colors[4]={0xff0000ff,0x00ff00ff,0x0000ffff,0xffffffff};
            for(unsigned y=0;y<8;y++) for(unsigned x=0;x<8;x++) {
                unsigned dy=7-y,m=0;
                for(unsigned bit=0;bit<3;bit++) m|=((x>>bit)&1)<<(2*bit)|((dy>>bit)&1)<<(2*bit+1);
                ((u32*)textures[i].data)[m]=colors[(y>=4)*2+(x>=4)];
            }
            quad(vb+6*i,16,48,32,32);
        }
        GSPGPU_FlushDataCache(textures[i].data,textures[i].size);
    }
    free(bytes);bytes=NULL;memset(&pack,0,sizeof(pack));
    GSPGPU_FlushDataCache(vb,9*6*sizeof(*vb));
    C3D_AttrInfo* attr=C3D_GetAttrInfo();AttrInfo_Init(attr);
    AttrInfo_AddLoader(attr,0,GPU_FLOAT,3);AttrInfo_AddLoader(attr,1,GPU_FLOAT,2);
    C3D_BufInfo* buf=C3D_GetBufInfo();BufInfo_Init(buf);BufInfo_Add(buf,vb,sizeof(*vb),2,0x10);
    C3D_TexEnv* env=C3D_GetTexEnv(0);C3D_TexEnvInit(env);
    C3D_TexEnvSrc(env,C3D_Both,GPU_TEXTURE0,0,0);C3D_TexEnvFunc(env,C3D_Both,GPU_REPLACE);
    C3D_DepthTest(false,GPU_ALWAYS,GPU_WRITE_ALL);C3D_CullFace(GPU_CULL_NONE);
    C3D_AlphaTest(false,GPU_ALWAYS,0);
    C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,GPU_ONE,GPU_ZERO);
    fprintf(log,"uploaded_once=9 original_tiles=8 diagnostic_tiles=1 vertex_bytes=%zu command_bytes=65536 target_bytes=768000\nlinear_delta=%lu linear_free=%lu\n",9*6*sizeof(*vb),(unsigned long)(before-linearSpaceFree()),(unsigned long)linearSpaceFree());
    for(unsigned frame=0;frame<FRAMES && aptMainLoop();frame++) {
        hidScanInput();if(hidKeysDown()&KEY_START) break;
        if(!C3D_FrameBegin(C3D_FRAME_SYNCDRAW)) { fprintf(log,"ERROR frame\n");goto done; }
        C3D_RenderTargetClear(target,C3D_CLEAR_ALL,0x303030ff,0);C3D_FrameDrawOn(target);
        for(unsigned i=0;i<9;i++) { C3D_TexBind(0,&textures[i]);C3D_DrawArrays(GPU_TRIANGLES,6*i,6); }
        C3D_FrameEnd(0);completed=frame+1;
    }
    if(completed!=FRAMES) { status=2;goto done; }
    C3D_FrameSync();
    if(!C3D_FrameBegin(0)) { fprintf(log,"ERROR capture wait\n");goto done; }
    int captured=capture();C3D_FrameEnd(0);
    fprintf(log,"capture_swatches=%d\n",captured);if(!captured) goto done;
    status=0;
done:
    if(input) fclose(input);
    if(c3d) { C3D_FrameSync();C3D_Fini(); }
    for(unsigned i=0;i<allocated;i++) C3D_TexDelete(&textures[i]);
    if(vb) linearFree(vb);
    if(program_ready) shaderProgramFree(&program);
    if(dvlb) DVLB_Free(dvlb);
    free(bytes);
    if(log) {
        fprintf(log,"completed_frames=%u expected=%u\nexit_status=%d\n",completed,FRAMES,status);
        if(status==0) fprintf(log,"SWATCH_COMPLETE\n");
        if(fclose(log)) status=1;
    }
    gfxExit();return status;
}
