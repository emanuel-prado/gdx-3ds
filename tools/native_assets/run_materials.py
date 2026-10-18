#!/usr/bin/env python3
"""Compare real-texture unlit combiners within one RGB level.

The one-level gate is explicit for the two-stage PICA multiply-add rounding.
It is not original lighting, filtering, FLX, sampler or hardware acceptance.
"""
import argparse,hashlib,json,os,re,shutil,signal,subprocess,sys,time
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/native_assets'))
import compile_textures as textures
from run_azahar import group_alive
p=argparse.ArgumentParser(description='Bounded native unlit-material pixel oracle; emulator only.')
p.add_argument('label')
p.add_argument('--binary',type=Path,default=ROOT/'build-3ds-native/gdx-native-materials.3dsx')
p.add_argument('--pack',type=Path,default=ROOT/'dist/native/sdmc/3ds/gdiffuser-native-swatch/textures.gdns')
p.add_argument('--mesh',type=Path,default=ROOT/'dist/native/sdmc/3ds/gdiffuser-native/machine.gdnp')
p.add_argument('--archive',type=Path,default=ROOT/'dist/sdmc/3ds/gdiffuser/fzerox.o2r')
p.add_argument('--timeout',type=float,default=60)
p.add_argument('--expect-rejection',action='store_true')
a=p.parse_args()
if not re.fullmatch('[A-Za-z0-9_-]+',a.label):p.error('invalid label')
if not 1 <= a.timeout <= 300:p.error('timeout must be 1..300 seconds')
for f in (a.binary,a.pack,a.mesh):
    if not f.is_file():p.error(f'missing {f}')
out=ROOT/'experiments/local/native-materials'/a.label;out.mkdir(parents=True,exist_ok=False)
profile=out/'azahar';game=profile/'data/azahar-emu/sdmc/3ds/gdiffuser-native-materials';game.mkdir(parents=True)
shutil.copy2(a.pack,game/'textures.gdns')
shutil.copy2(a.mesh,game/'machine.gdnp')
cfg=profile/'config/azahar-emu';cfg.mkdir(parents=True)
(cfg/'qt-config.ini').write_text('[System]\nis_new_3ds=false\nis_new_3ds\\default=false\n[Debugging]\ninstant_debug_log=true\ninstant_debug_log\\default=false\n[Miscellaneous]\nlog_filter=*:Warning Debug.Emulated:Debug\nlog_filter\\default=false\n')
manifest=dict(diagnostic_only=True,binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest(),pack_sha256=hashlib.sha256(a.pack.read_bytes()).hexdigest(),mesh_sha256=hashlib.sha256(a.mesh.read_bytes()).hexdigest())
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
report=dict(passed=False)
with (out/'emulator.stdout.log').open('w') as stream:
    process=subprocess.Popen(['timeout','--signal=TERM','--kill-after=5s',f'{a.timeout+5}s','bash',str(ROOT/'tools/azahar.sh'),str(a.binary.resolve())],cwd=ROOT,env=dict(os.environ,GDX_AZAHAR_PROFILE=str(profile)),stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    report['test_pgid']=process.pid;start=time.monotonic()
    try:
        while time.monotonic()-start<a.timeout:
            log=game/'run.log'
            if log.exists() and 'exit_status=' in log.read_text():break
            if process.poll() is not None:raise RuntimeError('emulator exited without completion')
            time.sleep(.25)
        else:raise TimeoutError('swatch harness timeout')
    except (RuntimeError,TimeoutError) as exc:report['error']=str(exc)
    finally:
        if group_alive(process.pid):os.killpg(process.pid,signal.SIGTERM)
        until=time.monotonic()+5
        while group_alive(process.pid) and time.monotonic()<until:process.poll();time.sleep(.1)
        if group_alive(process.pid):os.killpg(process.pid,signal.SIGKILL)
        process.wait(timeout=5)
        until=time.monotonic()+1
        while group_alive(process.pid) and time.monotonic()<until:time.sleep(.1)
        report['cleanup_group_exited']=not group_alive(process.pid)
        if not report['cleanup_group_exited']:report['error']='test process group survived cleanup'
log=(game/'run.log').read_text() if (game/'run.log').exists() else ''
emulog=profile/'data/azahar-emu/log/azahar_log.txt'
if emulog.exists():
    shutil.copy2(emulog,out/'emulator.log')
    if re.search(r'Unmapped|\[Critical\]|\[Fatal\]',emulog.read_text(errors='replace'),re.I):report['error']='fatal or invalid memory diagnostic'
try:
    if 'error' not in report and a.expect_rejection:
        report['passed']=('exit_status=1' in log and 'uploaded_once=' not in log and
                          any(marker in log for marker in ['ERROR pack checksum','ERROR texture validation','ERROR unsupported material scene']))
        report['rejection_before_upload']=report['passed']
    elif 'error' not in report:
        if not all(m in log for m in ['completed_frames=360 expected=360','exit_status=0','MATERIAL_COMPLETE']):report['error']='missing completion'
        else:
            import csv,math
            game_rows=list(csv.DictReader((game/'frames.csv').open()))
            shots=[game/f'scene{i}.bmp' for i in range(4)]
            if len(game_rows)!=360 or [int(r['frame']) for r in game_rows]!=list(range(360)):report['error']='partial or unordered frames'
            elif not all(x.is_file() and x.stat().st_size==288054 for x in shots):report['error']='missing screenshots'
            elif shots[2].read_bytes()!=shots[3].read_bytes():report['error']='unstable material grid'
            elif len(set(shots[0].read_bytes()[54:]))<8:report['error']='empty or trivial machine render'
            elif not re.search(r'clip_crossing_triangles=[1-9][0-9]* ',log):report['error']='near plane not crossed'
            else:
                bmp=shots[2].read_bytes()
                if (bmp[:2]!=b'BM' or struct.unpack_from('<I',bmp,10)[0]!=54 or
                        struct.unpack_from('<iiHHI',bmp,18)!=(400,240,1,24,0)):
                    raise ValueError('invalid material screenshot')
                def pixel(xy):
                    x,y=xy;offset=54+((239-y)*400+x)*3
                    return tuple(bmp[offset:offset+3][::-1])
                seg=textures.read_source(a.archive)
                order=[1,2,3,4,5,6,7,0]
                prims=[(255,255,255),(255,255,0),(255,255,0),(255,255,255),(255,255,255),(255,255,255),(255,255,255),(209,238,255)]
                failures=[];hist={};checks=0
                for m,tile in enumerate(order):
                    _,symbol,off,fmt,tw,th,*_=textures.CATALOG[tile]
                    count=tw*th*2 if fmt=='RGBA16' else tw*th//2
                    rgba=textures.decode(seg[off:off+count],fmt,tw,th)
                    env=(0,0,255) if m<5 else (0,0,0) if m<7 else (14,99,165)
                    for sy in range(th):
                        for sx in range(tw):
                            dx=int((sx+.5)*80/tw);dy=int((sy+.5)*64/th)
                            tx=math.floor((dx+.5)/80*(tw-1/32));ty=math.floor((dy+.5)/64*(th-1/32))
                            t=rgba[(ty*tw+tx)*4:(ty*tw+tx)*4+4]
                            if m==0:expected=tuple((t[k]*t[3]+env[k]*(255-t[3]))//255 for k in range(3))
                            else:expected=tuple((prims[m][k]*t[k]+env[k]*(255-t[k]))//255 for k in range(3))
                            actual=pixel((8+(m%4)*98+dx,8+(m//4)*84+dy))
                            error=max(abs(expected[k]-actual[k]) for k in range(3));hist[error]=hist.get(error,0)+1;checks+=1
                            if error>1 and len(failures)<20:failures.append(dict(material=m,tile=tile,source_texel=[tx,ty],expected=expected,actual=actual,error=error))
                report.update(passed=not failures and report['cleanup_group_exited'],pixel_checks=checks,max_rgb_error=max(hist),error_histogram=hist,first_pixel_failures=failures)
except (OSError,ValueError,struct.error,KeyError) as exc:
    report.update(passed=False,error=str(exc))
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
