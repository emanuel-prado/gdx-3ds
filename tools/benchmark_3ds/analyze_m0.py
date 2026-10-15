#!/usr/bin/env python3
"""Summarize capture windows and compare selected semantic state tick-for-tick."""
import argparse
import csv
import json
import math
from pathlib import Path

STATE_FIELDS = ("tick", "mode", "course", "racers", "position_hash", "velocity_hash",
                "status_hash", "race_clock_hash", "state_hash", "rng_hash")


def read_capture(path):
    with Path(path).open() as stream:
        rows = list(csv.DictReader(line for line in stream if not line.startswith("#")))
    if not rows:
        raise ValueError(f"empty capture: {path}")
    ticks = [int(row["tick"]) for row in rows]
    if any(b <= a for a, b in zip(ticks, ticks[1:])):
        raise ValueError("capture ticks are not strictly increasing")
    for row in rows:
        for field in ("update_us", "draw_us", "gfx_us"):
            value = float(row[field])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid timing: {field}")
    return rows


def compare(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        for field in STATE_FIELDS:
            if field not in a and field not in b:
                continue  # original capture schema; aggregate state/RNG are still compared
            if field not in a or field not in b:
                return {"match": False, "reason": "capture schemas differ", "field": field}
            if a[field] != b[field]:
                return {"match": False, "index": i, "field": field,
                        "left": a[field], "right": b[field]}
    if len(left) != len(right):
        return {"match": False, "reason": "capture lengths differ",
                "left": len(left), "right": len(right)}
    return {"match": True, "samples": len(left),
            "scope": "selected racer/mode/RNG fields; not complete simulation equivalence"}


def summarize(rows):
    def group(samples):
        result = {"samples": len(samples)}
        if not samples:
            return result
        for key in ("update_us", "draw_us", "gfx_us"):
            values = sorted(float(row[key]) / 1000 for row in samples)
            result[key.replace("_us", "_ms")] = {
                "mean": sum(values) / len(values),
                **{name: values[int(p * (len(values) - 1))]
                   for name, p in (("p50", .5), ("p95", .95), ("p99", .99))},
                "max": values[-1],
            }
        return result
    return {"all": group(rows), "gp_30_racers": group([
        row for row in rows if int(row["mode"]) & 31 == 1 and int(row["racers"]) == 30]),
        "note": "elapsed section times include yields/preemption; emulator results are not OG timings"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture")
    parser.add_argument("--compare")
    parser.add_argument("--through-tick", type=int,
                        help="explicit inclusive tick window; applies equally to both captures")
    args = parser.parse_args()
    rows = read_capture(args.capture)
    if args.through_tick is not None:
        rows = [row for row in rows if int(row["tick"]) <= args.through_tick]
        if not rows:
            parser.error("selected tick window is empty")
    result = summarize(rows)
    if args.through_tick is not None:
        result["through_tick"] = args.through_tick
    if args.compare:
        other = read_capture(args.compare)
        if args.through_tick is not None:
            other = [row for row in other if int(row["tick"]) <= args.through_tick]
        result["comparison"] = compare(rows, other)
    print(json.dumps(result, indent=2))
    if args.compare and not result["comparison"]["match"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
