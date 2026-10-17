#!/usr/bin/env python3
"""Streaming M0.5 replay validation/comparison. No executable hash equality required."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAGIC = b'GDXRPL\x01\x00'
FIELDS = ('tick', 'mode', 'course', 'racers', 'state', 'rng', 'position', 'velocity',
          'status', 'race_clock', 'vi_tick', 'energy_attack', 'lod', 'camera_pause',
          'player_lap', 'player_finished', 'player_position', 'player_time',
          'player_laps_completed', 'results')


def checksum(h, data):
    for byte in data:
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return h


def metadata_identity(path):
    manifest = json.loads(Path(path).read_text())
    metadata = manifest['metadata']
    identity = hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if manifest['identity'] != identity or metadata['schema'] != 1:
        raise ValueError('metadata identity/schema mismatch')
    return identity


def records(path, identity=None, require_race=True):
    """Yield bounded records; fully exhausting the iterator validates the footer."""
    with Path(path).open('rb') as stream:
        header = stream.read(72)
        if len(header) != 72 or header[:8] != MAGIC:
            raise ValueError('invalid replay header/version')
        token = header[8:].decode('ascii')
        if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise ValueError('invalid metadata identity')
        if identity is not None and token != identity:
            raise ValueError('configuration/content identity mismatch')
        count, h, laps, last, course = 0, 2166136261, set(), None, None
        while True:
            kind = stream.read(1)
            if kind == b'\x01':
                payload = stream.read(100)
                if len(payload) != 100:
                    raise ValueError(f'truncated poll {count}')
                pads = tuple(struct.unpack_from('<HbbB', payload, 5*i) for i in range(4))
                if any(p[3] > 1 for p in pads):
                    raise ValueError(f'invalid controller presence at poll {count}')
                state = struct.unpack_from('<20I', payload, 20)
                if state[15] > 1 or state[19] > 1:
                    raise ValueError('invalid state boolean')
                if state[1] & 31 == 1 and state[3] == 30:
                    if course is None:
                        course = state[2]
                    if course != state[2]:
                        raise ValueError('multiple GP courses in one fixture')
                    laps.add(state[14])
                last = state
                h = checksum(h, kind + payload)
                yield count, pads, dict(zip(FIELDS, state))
                count += 1
            elif kind == b'\x02':
                footer = stream.read(13)
                if len(footer) != 13:
                    raise ValueError('truncated footer')
                expected, expected_hash, complete = struct.unpack('<QIB', footer)
                if expected != count or expected_hash != h or complete != 1 or stream.read(1):
                    raise ValueError('incomplete/corrupt endpoint or trailing data')
                if not count:
                    raise ValueError('empty session')
                if require_race and (not {1, 2, 3}.issubset(laps) or last[3] != 30 or
                                     last[1] & 31 != 1 or not last[15] or last[17] == 0 or
                                     last[18] != 4 or not last[19] or not 1 <= last[16] <= 30):
                    raise ValueError('endpoint does not verify a complete three-lap GP and results')
                return
            else:
                raise ValueError(f'missing footer/invalid record at poll {count}')


def validate(path, identity=None, require_race=True):
    count = 0
    for count, _, state in records(path, identity, require_race):
        pass
    return {'complete': True, 'polls': count + 1, 'endpoint': state}


def compare(reference, candidate, identity=None):
    # Validate both entire files first: a matching prefix is never accepted.
    a = validate(reference, identity)
    candidate_error = None
    try:
        b = validate(candidate, identity)
    except (ValueError, UnicodeError) as exc:
        b = None
        candidate_error = str(exc)
    first, compared = None, 0
    left, right = records(reference, identity), records(candidate, identity)
    try:
        for (poll, pads_a, state_a), (_, pads_b, state_b) in zip(left, right):
            compared = poll + 1
            values_a, values_b = {'input': pads_a, **state_a}, {'input': pads_b, **state_b}
            for field in values_a:
                if values_a[field] != values_b[field] and first is None:
                    first = {'match': False, 'poll': poll, 'tick': state_a['tick'],
                             'subsystem': field, 'reference': values_a[field], 'candidate': values_b[field]}
    except (ValueError, UnicodeError) as exc:
        candidate_error = str(exc)
    finally:
        left.close()
        right.close()
    if first:
        if candidate_error:
            first['completion_error'] = candidate_error
        return first
    if candidate_error:
        return {'match': False, 'subsystem': 'endpoint', 'poll': compared,
                'reference': 'verified race endpoint', 'candidate': candidate_error}
    if a['polls'] != b['polls']:
        return {'match': False, 'subsystem': 'endpoint', 'poll': min(a['polls'], b['polls']),
                'reference': a['polls'], 'candidate': b['polls']}
    return {'match': True, 'polls': a['polls'], 'scope': 'selected semantic fields through GP results'}


def summary(report):
    if report.get('match'):
        return f"MATCH: {report['polls']} polls through verified GP results"
    if 'subsystem' in report:
        return (f"DIVERGENCE poll={report['poll']} tick={report.get('tick', '?')} "
                f"{report['subsystem']}: {report['reference']} -> {report['candidate']}")
    return report.get('error', f"VALID: {report.get('polls', '?')} polls")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    parser.add_argument('--compare', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--manifest', type=Path, help='defaults to recording directory/manifest.json')
    args = parser.parse_args()
    try:
        identity = metadata_identity(args.manifest or args.recording.parent / 'manifest.json')
        if args.compare and metadata_identity(args.compare.parent / 'manifest.json') != identity:
            raise ValueError('candidate metadata mismatch')
        report = compare(args.recording, args.compare, identity) if args.compare else validate(args.recording, identity)
    except (ValueError, OSError, UnicodeError, KeyError) as exc:
        report = {'match': False, 'error': str(exc)}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(summary(report))
    return 0 if report.get('match', report.get('complete', False)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
