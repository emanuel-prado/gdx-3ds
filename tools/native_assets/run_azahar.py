#!/usr/bin/env python3
"""Run M1a in a fresh OG-profile Azahar instance; artifacts remain private."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def group_alive(pid):
    # killpg(0) includes already-exited zombie children; inspect live group members.
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal(): continue
        try:
            fields=(entry/'stat').read_text().rsplit(')',1)[1].split()
            if int(fields[2])==pid and fields[0] not in ('Z','X'):return True
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return False

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('label')
    p.add_argument('--pack',type=Path,default=ROOT/'dist/native/sdmc/3ds/gdiffuser-native/machine.gdnp')
    p.add_argument('--timeout',type=float,default=60)
    a=p.parse_args()
    if not 1 <= a.timeout <= 300:p.error('timeout must be 1..300 seconds')
    if not re.fullmatch('[A-Za-z0-9_-]+',a.label):p.error('invalid label')
    binary=ROOT/'build-3ds-native/gdx-native-m1a.3dsx'
    for f in [binary,a.pack]:
        if not f.is_file():p.error(f'missing {f}')
    output=ROOT/'experiments/local/native-m1a'/a.label
    output.mkdir(parents=True,exist_ok=False)
    profile=output/'azahar';game=profile/'data/azahar-emu/sdmc/3ds/gdiffuser-native'
    game.mkdir(parents=True)
    shutil.copy2(a.pack,game/'machine.gdnp')
    config=profile/'config/azahar-emu';config.mkdir(parents=True)
    (config/'qt-config.ini').write_text('[System]\nis_new_3ds=false\nis_new_3ds\\default=false\n[Debugging]\ninstant_debug_log=true\ninstant_debug_log\\default=false\n[Miscellaneous]\nlog_filter=*:Warning Debug.Emulated:Debug\nlog_filter\\default=false\n')
    manifest={'environment':'Azahar 2126.2 OG model; host emulator timings only','binary_sha256':digest(binary),'pack_sha256':digest(a.pack),'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    start=time.monotonic()
    failed=None
    with (output/'emulator.stdout.log').open('w') as stream:
        process=subprocess.Popen(['timeout','--signal=TERM','--kill-after=5s',f'{a.timeout+5}s','bash',str(ROOT/'tools/azahar.sh'),str(binary)],env=dict(os.environ,GDX_AZAHAR_PROFILE=str(profile)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while True:
                log=game/'run.log'
                if log.exists() and 'exit_status=' in log.read_text():break
                if process.poll() is not None:raise RuntimeError('emulator exited before completion')
                if time.monotonic()-start>a.timeout:raise TimeoutError('native harness timed out')
                time.sleep(0.25)
        except (RuntimeError,TimeoutError) as e:failed=str(e)
        finally:
            # Signal the test group even if its AppImage leader has exited.
            if group_alive(process.pid):os.killpg(process.pid,signal.SIGTERM)
            until=time.monotonic()+5
            while group_alive(process.pid) and time.monotonic()<until:
                process.poll();time.sleep(0.1)
            if group_alive(process.pid):os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=5)
            time.sleep(0.1)
            if group_alive(process.pid):failed='test process group survived cleanup'
    source_log=profile/'data/azahar-emu/log/azahar_log.txt'
    if source_log.exists():
        shutil.copy2(source_log,output/'emulator.log')
        if re.search(r'Unmapped|\[Critical\]|\[Fatal\]',source_log.read_text(errors='replace'),re.I):failed='fatal/invalid memory emulator diagnostic'
    report={'passed':False,'error':failed}
    if not failed:
        if 'exit_status=0' not in (game/'run.log').read_text():report['error']='guest rejected run'
        else:
            rows=list(csv.DictReader((game/'frames.csv').open()))
            report['frames']=len(rows)
            if len(rows)!=720:report['error']='partial CSV'
            else:
                # Pixel equality across reversed submission order proves depth wins.
                shots=[game/f'scene{i}.bmp' for i in range(4)]
                if not all(s.is_file() and s.stat().st_size==288054 for s in shots):
                    report['error']='missing/invalid screenshots'
                elif shots[2].read_bytes()!=shots[3].read_bytes():
                    report['error']='depth differs with submission order'
                elif len(set(shots[0].read_bytes()[54:]))<4:
                    report['error']='empty render'
                elif not re.search(r'clip_crossing_triangles=[1-9][0-9]* ',(game/'run.log').read_text()):
                    report['error']='near-plane crossing was not exercised'
                else:
                    report['passed']=True
                report['depth_order_identical']=all(s.is_file() for s in shots[2:]) and shots[2].read_bytes()==shots[3].read_bytes()
                report['timings']={}
                for key in ['cpu_work_ms','previous_gpu_queue_ms']:
                    values=sorted(float(r[key]) for r in rows[30:] if int(r['frame'])%240>5)
                    report['timings'][key]={'median':statistics.median(values),'p95':values[int(len(values)*.95)],'max':max(values)}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(output),**report},indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
