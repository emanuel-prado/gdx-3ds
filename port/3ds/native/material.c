#include <3ds.h>
#include <citro3d.h>
#include <malloc.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "material_shader_shbin.h"
#include "texture_pack.h"
#include "material_scene.h"
#include "pack.h"
#define DIR "sdmc:/3ds/gdiffuser-native-materials/"
#define FRAMES 360
#define COMMAND_BYTES (256*1024)
#define TRANSFER (GX_TRANSFER_FLIP_VERT(0)|GX_TRANSFER_OUT_TILED(0)|GX_TRANSFER_RAW_COPY(0)|GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8)|GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB8)|GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO))
static void set_material(const NativeMaterial* material) {
    for(unsigned i=0;i<6;i++) C3D_TexEnvInit(C3D_GetTexEnv(i));
    C3D_TexEnv* first=C3D_GetTexEnv(0);
    C3D_TexEnvColor(first,material->env);
    C3D_TexEnvSrc(first,C3D_Alpha,GPU_CONSTANT,0,0);
    C3D_TexEnvFunc(first,C3D_Alpha,GPU_REPLACE);
    if(material->combine==0) {
        // (T-E)*T.a+E = T*T.a + E*(1-T.a).
        C3D_TexEnvSrc(first,C3D_RGB,GPU_TEXTURE0,GPU_CONSTANT,GPU_TEXTURE0);
        C3D_TexEnvOpRgb(first,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_ALPHA);
        C3D_TexEnvFunc(first,C3D_RGB,GPU_INTERPOLATE);
    } else {
        // Stage 0: E*(1-T). Stage 1: T*P+previous.
        C3D_TexEnvSrc(first,C3D_RGB,GPU_CONSTANT,GPU_TEXTURE0,0);
        C3D_TexEnvOpRgb(first,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_ONE_MINUS_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR);
        C3D_TexEnvFunc(first,C3D_RGB,GPU_MODULATE);
        C3D_TexEnv* second=C3D_GetTexEnv(1);C3D_TexEnvColor(second,material->prim);
        C3D_TexEnvSrc(second,C3D_RGB,GPU_TEXTURE0,GPU_CONSTANT,GPU_PREVIOUS);
        C3D_TexEnvFunc(second,C3D_RGB,GPU_MULTIPLY_ADD);
        C3D_TexEnvSrc(second,C3D_Alpha,GPU_PREVIOUS,0,0);
        C3D_TexEnvFunc(second,C3D_Alpha,GPU_REPLACE);
    }
}
static void quad(NativeVertex* out,unsigned slot,unsigned width,unsigned height) {
    float x=8+(slot%4)*98,y=232-(slot/4)*84;
    const float positions[6][2]={{x,y},{x,y-64},{x+80,y},{x+80,y},{x,y-64},{x+80,y-64}};
    const unsigned uv[6][2]={{0,0},{0,1},{1,0},{1,0},{0,1},{1,1}};
    memset(out,0,6*sizeof(*out));
    for(unsigned i=0;i<6;i++) {
        out[i].position[0]=positions[i][0];out[i].position[1]=positions[i][1];
        out[i].uv[0]=(int16_t)(uv[i][0]*width*32);out[i].uv[1]=(int16_t)(uv[i][1]*height*32);
    }
}
static void hex(FILE* f,const unsigned char* b,size_t n) { for(size_t i=0;i<n;i++) fprintf(f,"%02x",b[i]); }
static void put32(unsigned char* b,unsigned v) { for(int i=0;i<4;i++) b[i]=(unsigned char)(v>>(i*8)); }
/* Read the completed displayed framebuffer; 3DS RGB8 layout is rotated BGR. */
static int capture(unsigned scene) {
    char path[128]; snprintf(path,sizeof(path),DIR "scene%u.bmp",scene);
    FILE* f=fopen(path,"wb"); if(!f) return 0;
    unsigned char header[54]={0},row[400*3]; header[0]='B';header[1]='M';
    put32(header+2,54+400*240*3);put32(header+10,54);put32(header+14,40);
    put32(header+18,400);put32(header+22,240);header[26]=1;header[28]=24;
    int ok=fwrite(header,1,54,f)==54;
    u8* fb=gfxGetFramebuffer(GFX_TOP,GFX_LEFT,NULL,NULL);
    for(int y=239;y>=0;y--) {
        for(int x=0;x<400;x++) memcpy(row+3*x,fb+3*(x*240+239-y),3);
        if(fwrite(row,1,sizeof(row),f)!=sizeof(row)) ok=0;
    }
    if(fclose(f)) ok=0;
    return ok;
}
int main(void) {
    gfxInitDefault(); gfxSet3D(false); consoleInit(GFX_BOTTOM,NULL);
    osSetSpeedupEnable(false);
    mkdir("sdmc:/3ds",0777); mkdir(DIR,0777);
    printf("Native textured-unlit Blue Falcon\nSHADE=1 FLX alpha=0 / nearest sampler\n%s\n",NATIVE_BUILD_ID);
    int status=1; void* bytes=NULL; NativeVertex* vb=NULL; NativeVertex* quad_vb=NULL; uint16_t* ib=NULL;
    FILE* log=fopen(DIR "run.log","w"); FILE* csv=NULL; FILE* input=NULL;
    C3D_RenderTarget* target=NULL; DVLB_s* dvlb=NULL; shaderProgram_s program={0};
    bool c3d=false,program_ready=false; NativeMesh mesh={0};
    C3D_Tex textures[8]={0};unsigned texture_count=0;void* texture_bytes=NULL;SwatchPack texture_pack={0};
    NativeMaterial materials[8];
    if(!log) { printf("Cannot write " DIR "run.log\n"); goto done; }
    fprintf(log,"toolchain=%s\n",NATIVE_TOOLCHAIN_ID);
    bool new3ds=false; APT_CheckNew3DS(&new3ds);
    fprintf(log,"build=%s\nsource=%s\ncompiler=%s\nmodel_new3ds=%d speedup_requested=0 stereo=0\n",NATIVE_BUILD_ID,NATIVE_SOURCE_ID,__VERSION__,new3ds);
    input=fopen(DIR "machine.gdnp","rb");
    if(!input || fseek(input,0,SEEK_END)) { fprintf(log,"ERROR pack open/seek\n"); goto done; }
    long size=ftell(input);
    if(size<192 || size>(long)NATIVE_PACK_MAX || fseek(input,0,SEEK_SET)) { fprintf(log,"ERROR pack size\n"); goto done; }
    bytes=malloc((size_t)size);
    if(!bytes || fread(bytes,1,(size_t)size,input)!=(size_t)size) { fprintf(log,"ERROR pack read/allocation\n"); goto done; }
    fclose(input); input=NULL;
    const char* error=native_pack_validate(bytes,(size_t)size,&mesh);
    if(error) { fprintf(log,"ERROR pack %s\n",error); goto done; }
    fprintf(log,"pack_crc32=%08lx pack_bytes=%ld\nrom_sha1=",(unsigned long)mesh.crc,size);hex(log,(unsigned char*)bytes+48,20);
    fprintf(log,"\nsegment_sha256=");hex(log,(unsigned char*)bytes+68,32);
    fprintf(log,"\nrecipe_sha256=");hex(log,(unsigned char*)bytes+100,32);
    fprintf(log,"\ncompiler_sha256=");hex(log,(unsigned char*)bytes+132,32);fprintf(log,"\n");
    if(material_scene_prepare(mesh.materials,mesh.material_count,materials)) { fprintf(log,"ERROR unsupported material scene\n");goto done; }
    fprintf(log,"scene=%s shade_rgb=1,1,1 q_flx=0 stock_initial_env=0,0,255 sampler=nearest_clampS_wrapT127\n",MATERIAL_SCENE_ID);
    input=fopen(DIR "textures.gdns","rb");
    if(!input || fseek(input,0,SEEK_END) || ftell(input)!=(long)SWATCH_PACK_BYTES || fseek(input,0,SEEK_SET)) { fprintf(log,"ERROR texture input size/open\n");goto done; }
    texture_bytes=malloc(SWATCH_PACK_BYTES);
    if(!texture_bytes || fread(texture_bytes,1,SWATCH_PACK_BYTES,input)!=SWATCH_PACK_BYTES) { fprintf(log,"ERROR texture read\n");goto done; }
    fclose(input);input=NULL;
    error=swatch_pack_validate(texture_bytes,SWATCH_PACK_BYTES,&texture_pack);
    if(error) { fprintf(log,"ERROR texture validation %s\n",error);goto done; }
    fprintf(log,"texture_crc32=%08lx\n",(unsigned long)texture_pack.crc);
    size_t vb_size=mesh.vertex_count*sizeof(*vb),ib_size=mesh.index_count*sizeof(*ib);
    u32 linear_start=linearSpaceFree();
    c3d=C3D_Init(COMMAND_BYTES); if(!c3d) { fprintf(log,"ERROR C3D init\n");goto done; }
    target=C3D_RenderTargetCreate(240,400,GPU_RB_RGBA8,GPU_RB_DEPTH24_STENCIL8);
    if(!target) { fprintf(log,"ERROR target allocation\n");goto done; }
    C3D_RenderTargetSetOutput(target,GFX_TOP,GFX_LEFT,TRANSFER);
    dvlb=DVLB_ParseFile((u32*)material_shader_shbin,material_shader_shbin_size);
    if(!dvlb || shaderProgramInit(&program)<0) { fprintf(log,"ERROR shader\n");goto done; }
    program_ready=true;
    if(shaderProgramSetVsh(&program,&dvlb->DVLE[0])<0) { fprintf(log,"ERROR shader bind\n");goto done; }
    C3D_BindProgram(&program);
    int projection=shaderInstanceGetUniformLocation(program.vertexShader,"projection");
    int modelview=shaderInstanceGetUniformLocation(program.vertexShader,"modelview");
    int texscale=shaderInstanceGetUniformLocation(program.vertexShader,"texscale");
    if(projection<0 || modelview<0 || texscale<0) { fprintf(log,"ERROR shader uniforms\n");goto done; }
    vb=linearAlloc(vb_size); ib=linearAlloc(ib_size);quad_vb=linearAlloc(8*6*sizeof(*quad_vb));
    if(!vb || !ib || !quad_vb) { fprintf(log,"ERROR GPU buffers\n");goto done; }
    memcpy(vb,mesh.vertices,vb_size);memcpy(ib,mesh.indices,ib_size);
    // Only immutable GPU copies remain referenced by submissions. Materials/bounds copied below.
    for(unsigned i=0;i<8;i++) {
        const SwatchTexture* t=&texture_pack.tiles[i];
        if(!C3D_TexInit(&textures[i],t->width,t->height,GPU_RGBA8)) { fprintf(log,"ERROR texture GPU allocation\n");goto done; }
        texture_count++;memcpy(textures[i].data,t->pixels,t->bytes);
        C3D_TexSetFilter(&textures[i],GPU_NEAREST,GPU_NEAREST);
        C3D_TexSetWrap(&textures[i],GPU_CLAMP_TO_EDGE,(i==1 || i==2 || i==7)?GPU_REPEAT:GPU_CLAMP_TO_EDGE);
        GSPGPU_FlushDataCache(textures[i].data,textures[i].size);
    }
    free(texture_bytes);texture_bytes=NULL;memset(&texture_pack,0,sizeof(texture_pack));
    fprintf(log,"uploaded_once=8 texture_gpu_bytes=18432 vertex_colors_ignored=1\n");
    for(unsigned i=0;i<8;i++) quad(quad_vb+6*i,i,textures[materials[i].tile].width,textures[materials[i].tile].height);
    GSPGPU_FlushDataCache(quad_vb,8*6*sizeof(*quad_vb));
    free(bytes); bytes=NULL;mesh.vertices=NULL;mesh.indices=NULL;mesh.materials=NULL;
    GSPGPU_FlushDataCache(vb,vb_size);GSPGPU_FlushDataCache(ib,ib_size);
    C3D_AttrInfo* attr=C3D_GetAttrInfo();AttrInfo_Init(attr);
    AttrInfo_AddLoader(attr,0,GPU_FLOAT,3);AttrInfo_AddLoader(attr,1,GPU_FLOAT,4);
    AttrInfo_AddLoader(attr,2,GPU_UNSIGNED_BYTE,4);AttrInfo_AddLoader(attr,3,GPU_SHORT,2);
    C3D_BufInfo* buf=C3D_GetBufInfo();BufInfo_Init(buf);BufInfo_Add(buf,vb,sizeof(*vb),4,0x3210);
    C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,GPU_ONE,GPU_ZERO);
    C3D_AlphaTest(false,GPU_ALWAYS,0);
    // PICA projection maps near to 0 and far to -w: reversed depth with clear=0.
    C3D_DepthTest(true,GPU_GEQUAL,GPU_WRITE_ALL); C3D_CullFace(GPU_CULL_BACK_CCW);
    C3D_Mtx proj; Mtx_PerspTilt(&proj,C3D_AngleFromDegrees(55),400.0f/240.0f,10.0f,4000.0f,false);
    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,projection,&proj);
    struct mallinfo heap=mallinfo();
    fprintf(log,"vertices=%lu indices=%lu triangles=%lu materials=%lu\nvbo_bytes=%zu ibo_bytes=%zu pack_transient_bytes=%ld command_bytes=%u\nlinear_delta=%lu linear_free=%lu target_color_depth_bytes=768000 vram_free=%lu heap_live=%d\n",
        (unsigned long)mesh.vertex_count,(unsigned long)mesh.index_count,(unsigned long)(mesh.index_count/3),(unsigned long)mesh.material_count,
        vb_size,ib_size,size,COMMAND_BYTES,(unsigned long)(linear_start-linearSpaceFree()),(unsigned long)linearSpaceFree(),(unsigned long)vramSpaceFree(),heap.uordblks);
    csv=fopen(DIR "frames.csv","w"); if(!csv) { fprintf(log,"ERROR CSV open\n"); goto done; }
    fprintf(csv,"frame,scene,cpu_work_ms,c3d_processing_ms,previous_gpu_queue_ms,linear_free,heap_live,command_usage\n");
    bool paused=false; float angle=0; unsigned completed=0;
    printf("START exit / A pause / Dpad rotate\n360 frames: orbit, clip, material grid\n");
    for(unsigned frame=0;frame<FRAMES && aptMainLoop();frame++) {
        hidScanInput();u32 down=hidKeysDown(),held=hidKeysHeld();if(down&KEY_START) break;
        if(down&KEY_A) paused=!paused;
        if(!paused) angle=frame*0.015f;
        if(held&KEY_LEFT) angle-=0.04f;
        if(held&KEY_RIGHT) angle+=0.04f;
        unsigned scene=frame/120;
        C3D_Mtx clip_view;
        if(!C3D_FrameBegin(C3D_FRAME_SYNCDRAW)) { fprintf(log,"ERROR frame begin\n");goto done; }
        float previous_gpu=C3D_GetDrawingTime();
        u64 start=svcGetSystemTick();
        C3D_RenderTargetClear(target,C3D_CLEAR_ALL,0x201810ff,0);
        C3D_FrameDrawOn(target);
        float distance=scene==1 ? 360.0f-440.0f*((frame%120)/119.0f) : 650.0f;
        if(scene==2) {
            C3D_Mtx ortho,identity;Mtx_OrthoTilt(&ortho,0,400,0,240,-1,1,false);Mtx_Identity(&identity);
            C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,projection,&ortho);
            C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,modelview,&identity);
            C3D_CullFace(GPU_CULL_NONE);C3D_DepthTest(false,GPU_ALWAYS,GPU_WRITE_ALL);
            buf=C3D_GetBufInfo();BufInfo_Init(buf);BufInfo_Add(buf,quad_vb,sizeof(*quad_vb),4,0x3210);
            for(unsigned m=0;m<8;m++) {
                unsigned tile=materials[m].tile;
                C3D_FVUnifSet(GPU_VERTEX_SHADER,texscale,1.0f/(32*textures[tile].width),1.0f/(32*textures[tile].height),0,0);
                C3D_TexBind(0,&textures[tile]);set_material(&materials[m]);
                C3D_DrawArrays(GPU_TRIANGLES,6*m,6);
            }
        } else {
        // Object/camera subtraction happens before conversion to float.
        double origin=1000000000.0,camera=1000000000.0;
        for(int draw=0;draw<(scene==2?2:1);draw++) {
            int instance=scene==2 && frame%120>=60 ? 1-draw : draw;
            // Both overlapping instances retain identical diagnostic materials.
            C3D_Mtx mv;Mtx_Identity(&mv);
            Mtx_Translate(&mv,(float)(origin-camera)+(instance?65:0),-35,-distance-(instance?100:0),true);
            Mtx_RotateX(&mv,0.40f,true);Mtx_RotateY(&mv,scene==1?0.55f:scene==2?0.65f:angle,true);
            C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,modelview,&mv);
            if(frame==165) clip_view=mv;
            for(unsigned m=0;m<mesh.material_count;m++) {
                unsigned tile=materials[m].tile;
                C3D_FVUnifSet(GPU_VERTEX_SHADER,texscale,1.0f/(32*textures[tile].width),1.0f/(32*textures[tile].height),0,0);
                C3D_TexBind(0,&textures[tile]);set_material(&materials[m]);
                C3D_DrawElements(GPU_TRIANGLES,materials[m].count,C3D_UNSIGNED_SHORT,ib+materials[m].first);
            }
        }
        }
        C3D_FrameEnd(0);
        double cpu=(svcGetSystemTick()-start)*1000.0/SYSCLOCK_ARM11;
        if(frame==165) {
            // Diagnostic only, after timing: prove real triangles straddle near.
            unsigned crossing=0,behind=0;float min_depth=INFINITY,max_depth=-INFINITY;
            for(unsigned tri=0;tri<mesh.index_count;tri+=3) {
                unsigned outside=0;
                for(unsigned corner=0;corner<3;corner++) {
                    const float* v=vb[ib[tri+corner]].position;
                    C3D_FVec eye=Mtx_MultiplyFVecH(&clip_view,FVec3_New(v[0],v[1],v[2]));
                    float depth=-eye.z; if(depth<10) outside++;
                    min_depth=fminf(min_depth,depth);max_depth=fmaxf(max_depth,depth);
                }
                if(outside && outside<3) crossing++;
                if(outside==3) behind++;
            }
            fprintf(log,"clip_crossing_triangles=%u clip_all_behind=%u eye_depth_min=%.3f eye_depth_max=%.3f\n",crossing,behind,min_depth,max_depth);
        }
        heap=mallinfo();
        // SD and console diagnostics intentionally outside the timed frame window.
        if(fprintf(csv,"%u,%u,%.6f,%.6f,%.6f,%lu,%d,%.6f\n",frame,scene,cpu,C3D_GetProcessingTime(),previous_gpu,(unsigned long)linearSpaceFree(),heap.uordblks,C3D_GetCmdBufUsage())<0) { fprintf(log,"ERROR CSV write\n");goto done; }
        if(frame%60==0) printf("\x1b[6;1Hframe %u scene %u\nCPU %.3f GPU queue %.3f ms\nlinear free %lu\n",frame,scene,cpu,previous_gpu,(unsigned long)linearSpaceFree());
        if(frame==60 || frame==165 || frame==260 || frame==320) {
            C3D_FrameSync(); // display transfer/presentation; FrameBegin below also waits GX completion
            if(!C3D_FrameBegin(0)) goto done;
            int ok=capture(frame==320?3:scene);C3D_FrameEnd(0);
            fprintf(log,"capture_scene%u=%d frame=%u distance=%.3f near=10 far=4000\n",frame==320?3:scene,ok,frame,distance);
            if(!ok) goto done;
        }
        completed=frame+1;
    }
    fprintf(log,"completed_frames=%u expected=%u\n",completed,FRAMES);
    status=completed==FRAMES?0:2;
done:
    if(input) fclose(input);
    if(csv && fclose(csv)) status=1;
    if(c3d) { C3D_FrameSync(); C3D_Fini(); } // drains outstanding GPU work before buffer release
    for(unsigned i=0;i<texture_count;i++) C3D_TexDelete(&textures[i]);
    free(texture_bytes);
    if(ib) linearFree(ib);
    if(vb) linearFree(vb);
    if(quad_vb) linearFree(quad_vb);
    // C3D_Fini owns remaining render targets.
    if(program_ready) shaderProgramFree(&program);
    if(dvlb) DVLB_Free(dvlb);
    free(bytes);
    if(log) { fprintf(log,"exit_status=%d\n",status);if(status==0) fprintf(log,"MATERIAL_COMPLETE\n"); if(fclose(log)) status=1; }
    gfxExit(); return status;
}
