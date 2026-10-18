#!/usr/bin/env python3
"""Run the native texture upload oracle; generated artifacts remain private.

Exact RGB checks cover storage/decode/upload under nearest/clamp/opaque state.
They do not qualify machine combiner, sampler parity, lighting or OG speed.
"""
import argparse,hashlib,json,os,re,shutil,signal,subprocess,sys,time
from pathlib import Path
import struct
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/native_assets'))
import compile_textures as textures
from run_azahar import group_alive
p=argparse.ArgumentParser(description='Bounded OG-profile texture upload and exact RGB oracle; emulator only.')
p.add_argument('label')
p.add_argument('--binary',type=Path,default=ROOT/'build-3ds-native/gdx-native-swatch.3dsx')
p.add_argument('--pack',type=Path,default=ROOT/'dist/native/sdmc/3ds/gdiffuser-native-swatch/textures.gdns')
p.add_argument('--archive',type=Path,default=ROOT/'dist/sdmc/3ds/gdiffuser/fzerox.o2r')
p.add_argument('--timeout',type=float,default=60)
p.add_argument('--expect-rejection',action='store_true',help='Require validation failure before any GPU upload')
a=p.parse_args()
if not re.fullmatch('[A-Za-z0-9_-]+',a.label):p.error('invalid label')
if not 1 <= a.timeout <= 300:p.error('timeout must be 1..300 seconds')
for f in (a.binary,a.pack):
    if not f.is_file():p.error(f'missing {f}')
out=ROOT/'experiments/local/native-swatch'/a.label;out.mkdir(parents=True,exist_ok=False)
profile=out/'azahar';game=profile/'data/azahar-emu/sdmc/3ds/gdiffuser-native-swatch';game.mkdir(parents=True)
shutil.copy2(a.pack,game/'textures.gdns')
cfg=profile/'config/azahar-emu';cfg.mkdir(parents=True)
(cfg/'qt-config.ini').write_text('[System]\nis_new_3ds=false\nis_new_3ds\\default=false\n[Debugging]\ninstant_debug_log=true\ninstant_debug_log\\default=false\n[Miscellaneous]\nlog_filter=*:Warning Debug.Emulated:Debug\nlog_filter\\default=false\n')
manifest=dict(diagnostic_only=True,binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest(),pack_sha256=hashlib.sha256(a.pack.read_bytes()).hexdigest())
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
        report['passed']=('ERROR validation ' in log and 'exit_status=1' in log and 'uploaded_once=' not in log)
        report['rejection_before_upload']=report['passed']
    elif 'error' not in report:
        markers=['completed_frames=120 expected=120','exit_status=0','SWATCH_COMPLETE','capture_swatches=1']
        if not all(m in log for m in markers):report['error']='missing completion markers'
        else:
            bmp=(game/'swatches.bmp').read_bytes()
            if (len(bmp)!=288054 or bmp[:2]!=b'BM' or
                struct.unpack_from('<I',bmp,10)[0]!=54 or
                struct.unpack_from('<iiHHI',bmp,18)!=(400,240,1,24,0)):
                raise ValueError('invalid screenshot format')
            def pixel(xy):
                x,y=xy;offset=54+((239-y)*400+x)*3
                return tuple(bmp[offset:offset+3][::-1])
            segment=textures.read_source(a.archive)
            rects=[(8,8,64,64),(106,8,64,64),(204,8,64,64),(302,8,64,64),(8,92,80,20),(106,92,32,64),(204,92,64,64),(302,92,64,64)]
            failures=[];checks=0
            for catalog,(x0,y0,w,h) in zip(textures.CATALOG,rects):
                tile,symbol,off,fmt,tw,th,*_=catalog
                n=tw*th*2 if fmt=='RGBA16' else tw*th//2
                data=textures.decode(segment[off:off+n],fmt,tw,th)
                for sy in range(th):
                    for sx in range(tw):
                        dx=int((sx+.5)*w/tw);dy=int((sy+.5)*h/th)
                        tx=int((dx+.5)*tw/w);ty=int((dy+.5)*th/h)
                        expected=tuple(data[(ty*tw+tx)*4:(ty*tw+tx)*4+3]);actual=pixel((x0+dx,y0+dy));checks+=1
                        if actual!=expected and len(failures)<20:failures.append(dict(tile=tile,screen=[x0+dx,y0+dy],texel=[tx,ty],expected=expected,actual=actual))
            marker=[((24,200),(255,0,0)),((40,200),(0,255,0)),((24,216),(0,0,255)),((40,216),(255,255,255))]
            for xy,expected in marker:
                actual=pixel(xy);checks+=1
                if actual!=expected:failures.append(dict(marker=xy,expected=expected,actual=actual))
            report.update(pixel_checks=checks,first_pixel_failures=failures,passed=not failures and report['cleanup_group_exited'])
except (OSError,ValueError,struct.error) as exc:
    report.update(passed=False,error=str(exc))
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
