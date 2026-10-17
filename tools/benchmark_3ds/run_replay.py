#!/usr/bin/env python3
"""Record a manual race or replay a fixture in a fresh isolated Azahar profile."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from replay import compare, summary, validate
from run_m0 import ROOT, digest

# This contract is hashed separately from executable provenance. Changes to this
# boot/configuration contract require a new fixture, renderer implementations do not.
CONFIG = ('[debug]\nrenderthread=0\ngputrace=0\nverbose=0\nfilelog=0\ndiag_audio=0\n'
          '[perf]\nrival_detail=0\nrival_detail_auto=0\n[stereo]\nenabled=0\n'
          '[audio]\nlle=0\n[menu]\nenabled=0\n')


def token(metadata):
    return hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def run(args):
    binary = args.binary.resolve()
    source_sd = args.source_sd.resolve()
    assets = [source_sd / '3ds/gdiffuser/fzerox.o2r',
              source_sd / '3ds/gdiffuser/gdiffuser.o2r', source_sd / '3ds/dspfirm.cdc']
    for path in [binary, *assets]:
        if not path.is_file():
            raise ValueError(f'required input missing: {path}')
    metadata = {'schema': 1, 'content': 'USA rev0 cartridge',
                'assets': {str(p.relative_to(source_sd)): digest(p) for p in assets},
                'config': CONFIG, 'rng1': {'seed': 12345, 'mask': 24690},
                'rng2': {'seed': 135780, 'mask': 67890},
                'initial_state': 'cold boot, empty saves, no savestate, no race-init frame reset',
                'endpoint': '30-racer three-lap GP, player finished, ranking screen reached',
                'poll_state': 'pre-input, all four controllers; semantic schema 20 words'}
    identity = token(metadata)
    if args.fixture:
        fixture = args.fixture.resolve()
        manifest = json.loads((fixture / 'manifest.json').read_text())
        if manifest['metadata'] != metadata or manifest['identity'] != identity:
            raise ValueError('fixture content/configuration mismatch')
        validate(fixture / 'capture.gdr', identity)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    profile = output / 'azahar'
    sd = profile / 'data/azahar-emu/sdmc'
    game = sd / '3ds/gdiffuser'
    game.mkdir(parents=True)
    cfg = profile / 'config/azahar-emu'
    cfg.mkdir(parents=True)
    (cfg / 'qt-config.ini').write_text(
        '[System]\nis_new_3ds=true\nis_new_3ds\\default=false\n'
        '[Debugging]\ninstant_debug_log=true\ninstant_debug_log\\default=false\n'
        '[Miscellaneous]\nlog_filter=*:Warning Debug.Emulated:Debug\nlog_filter\\default=false\n')
    for path in assets:
        (sd / path.relative_to(source_sd)).symlink_to(path)
    (game / 'replay-identity.txt').write_text(identity)
    (game / 'gdiffuser.ini').write_text(CONFIG +
        f'[replay]\nmode={2 if args.fixture else 1}\ngraphics={2 if args.graphics == "bypass" else 1}\n')
    if args.fixture:
        shutil.copy2(fixture / 'capture.gdr', game / 'session.gdr')
    provenance = {'binary': str(binary), 'sha256': digest(binary), 'graphics': args.graphics,
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    (output / 'manifest.json').write_text(json.dumps(
        {'identity': identity, 'metadata': metadata, 'provenance': provenance}, indent=2) + '\n')
    capture = game / 'capture.gdr'
    env = dict(os.environ, GDX_AZAHAR_PROFILE=str(profile))
    start = time.monotonic()
    log_offset, log_tail = 0, ""
    with (output / 'emulator.stdout.log').open('w') as log:
        process = subprocess.Popen(['bash', str(ROOT / 'tools/azahar.sh'), str(binary)], cwd=ROOT,
                                   env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while not capture.exists():
                if process.poll() is not None:
                    raise RuntimeError(f'emulator exited before capture ({process.returncode})')
                if time.monotonic() - start > args.timeout:
                    raise TimeoutError(f'capture timeout after {args.timeout}s')
                live_log = profile / 'data/azahar-emu/log/azahar_log.txt'
                if live_log.exists():
                    with live_log.open(errors='replace') as live:
                        live.seek(log_offset)
                        chunk = live.read()
                        log_offset = live.tell()
                    log_tail = (log_tail + chunk)
                    if '[replay] ERROR' in log_tail:
                        receipt = next(line for line in log_tail.splitlines() if '[replay] ERROR' in line)
                        raise RuntimeError(receipt)
                    log_tail = log_tail[-256:]
                time.sleep(.25)
            shutil.copy2(capture, output / 'capture.gdr')
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            emulator_log = profile / 'data/azahar-emu/log/azahar_log.txt'
            if emulator_log.exists():
                shutil.copy2(emulator_log, output / 'emulator.log')
    capture = output / 'capture.gdr'
    return compare(fixture / 'capture.gdr', capture, identity) if args.fixture else validate(capture, identity)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='new local artifact directory')
    parser.add_argument('--fixture', type=Path, help='recording directory; omit to record live input')
    parser.add_argument('--binary', type=Path,
                        default=ROOT / 'build-3ds-benchmark/port/3ds/G-Diffuser-3DS.3dsx')
    parser.add_argument('--source-sd', type=Path,
                        default=ROOT / 'experiments/local/azahar/data/azahar-emu/sdmc')
    parser.add_argument('--graphics', choices=('render', 'bypass'), default='render')
    parser.add_argument('--timeout', type=float, default=1800)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a new directory')
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    try:
        report = run(args)
    except (OSError, ValueError, RuntimeError, TimeoutError, KeyError) as exc:
        report = {'match': False, 'error': str(exc)}
    if args.output.is_dir():
        (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(summary(report))
    return 0 if report.get('match', report.get('complete', False)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
