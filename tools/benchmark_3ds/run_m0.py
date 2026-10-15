#!/usr/bin/env python3
"""Run a controlled GP start in a fresh isolated Azahar profile.

Captures verify the diagnostic path; emulator timings are not OG CPU measurements.
Assets and DSP firmware must already be staged using docs/LOCAL-SETUP.md.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--mode", choices=["render", "bypass"], required=True)
    parser.add_argument("--frames", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("label must contain letters, digits, underscores or hyphens")
    if not 64 <= args.frames <= 8192:
        parser.error("frames must be between 64 and 8192")
    binary = ROOT / "build-3ds-benchmark/port/3ds/G-Diffuser-3DS.3dsx"
    source_sd = ROOT / "experiments/local/azahar/data/azahar-emu/sdmc"
    assets = [source_sd / "3ds/gdiffuser/fzerox.o2r",
              source_sd / "3ds/gdiffuser/gdiffuser.o2r", source_sd / "3ds/dspfirm.cdc"]
    for path in [binary, *assets]:
        if not path.is_file():
            parser.error(f"required input missing: {path}")
    output = ROOT / "experiments/local/m0" / args.label
    output.mkdir(parents=True, exist_ok=False)
    profile = output / "azahar"
    sd = profile / "data/azahar-emu/sdmc"
    game = sd / "3ds/gdiffuser"
    game.mkdir(parents=True)
    config = profile / "config/azahar-emu"
    config.mkdir(parents=True)
    (config / "qt-config.ini").write_text(
        "[System]\nis_new_3ds=true\nis_new_3ds\\default=false\n"
        "[Debugging]\ninstant_debug_log=true\ninstant_debug_log\\default=false\n"
        "[Miscellaneous]\nlog_filter=*:Warning Debug.Emulated:Debug\n"
        "log_filter\\default=false\n")
    for path in assets:
        target = sd / path.relative_to(source_sd)
        target.symlink_to(path)
    (game / "gdiffuser.ini").write_text(
        f"[benchmark]\nmode={1 if args.mode == 'render' else 2}\nframes={args.frames}\nrace_only=1\n"
        "[debug]\nrenderthread=0\ngputrace=0\nverbose=0\nfilelog=0\n"
        "diag_audio=0\n[perf]\nrival_detail=0\nrival_detail_auto=0\n"
        "[stereo]\nenabled=0\n[audio]\nlle=0\n")
    (game / "benchmark-input.txt").write_text(
        "WAIT 300\nWAITMODE 0 900\nWAIT 60\nPRESS START 2\n"
        "WAITMODE 7 900\nWAIT 90\nPRESS A 2\nWAIT 90\nPRESS A 2\nWAIT 90\nPRESS A 2\n"
        "WAITMODE 10 900\nWAIT 90\nPRESS A 2\nWAIT 90\nPRESS A 2\n"
        "WAITMODE 8 900\nWAIT 90\nPRESS A 2\nWAIT 90\nPRESS A 2\n"
        "WAITMODE 9 900\nWAIT 90\nPRESS A 2\nWAIT 90\nPRESS A 2\n"
        "WAITMODE 1 900\nINPUT A 0 0 30000\n")
    manifest = {
        "label": args.label, "mode": args.mode, "frames": args.frames,
        "scenario": "gp-start-straight-acceleration", "hardware": "Azahar New3DS proxy",
        "race_init_frame_reset": True,
        "seed1": 12345, "seed2": 67890,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": {str(p.relative_to(ROOT)): digest(p) for p in [binary, *assets]},
        "diagnostic_sources": {str(p.relative_to(ROOT)): digest(p) for p in [
            ROOT / "port/3ds/gdx3ds_benchmark.cpp",
            ROOT / "port/3ds/game/gdx3ds_benchmark_state.c"]},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    env = dict(os.environ, GDX_AZAHAR_PROFILE=str(profile))
    capture = game / "benchmark.csv"
    start = time.monotonic()
    with (output / "emulator.stdout.log").open("w") as log:
        process = subprocess.Popen(["bash", str(ROOT / "tools/azahar.sh"), str(binary)],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            while not capture.exists():
                if process.poll() is not None:
                    raise RuntimeError(f"emulator exited before capture: {process.returncode}")
                if time.monotonic() - start > args.timeout:
                    raise TimeoutError(f"capture did not complete in {args.timeout} seconds")
                live_log = profile / "data/azahar-emu/log/azahar_log.txt"
                if live_log.exists() and '[autotest] WAITMODE timeout' in live_log.read_text(errors='replace'):
                    raise RuntimeError('menu-navigation script timed out; capture rejected')
                time.sleep(0.5)
            shutil.copy2(capture, output / "benchmark.csv")
            with capture.open() as stream:
                rows = list(csv.DictReader(line for line in stream if not line.startswith("#")))
            if len(rows) != args.frames:
                raise RuntimeError(f"partial capture: {len(rows)} of {args.frames} samples")
            if any(int(row['mode']) & 31 != 1 or int(row['racers']) != 30 for row in rows):
                raise RuntimeError('capture includes samples outside the 30-racer GP')
            if any(int(row['course']) != 0 for row in rows):
                raise RuntimeError('expected the first Jack Cup course; capture rejected')
            time.sleep(2)  # allow guest teardown and the final log receipts to finish
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            source_log = profile / "data/azahar-emu/log/azahar_log.txt"
            if source_log.exists():
                shutil.copy2(source_log, output / "emulator.log")
    print(f"Saved {output / 'benchmark.csv'}", flush=True)


if __name__ == "__main__":
    main()
