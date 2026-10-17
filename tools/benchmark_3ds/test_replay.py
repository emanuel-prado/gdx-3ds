import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from replay import checksum, compare, records, validate, metadata_identity, MAGIC
from run_replay import token

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = 'a' * 64


class Pad(C.Structure):
    _fields_ = [('buttons', C.c_ushort), ('stickX', C.c_byte), ('stickY', C.c_byte)]


def state(i, final=False):
    # Duplicate ticks intentionally: a poll need not advance the game.
    return [i//3, 1, 0, 30, 42, 43, 44, 45, 46, 47, i,
            48, 49, 50, min(i+1, 4), int(final), 2, i+1, 4 if final else 1, int(final)]


def write_fixture(path, count=9, change=None):
    h = 2166136261
    with path.open('wb') as f:
        f.write(MAGIC + IDENTITY.encode())
        for i in range(count):
            s = state(i, i == count-1)
            if change and i == change[0]:
                s[change[1]] += 1
            block = b'\x01' + struct.pack('<HbbB', 0x8020 if i % 2 else 0, -128+i, 127-i, 1)
            block += struct.pack('<HbbB', 0, 0, 0, 0) * 3
            block += struct.pack('<20I', *s)
            h = checksum(h, block)
            f.write(block)
        f.write(b'\x02' + struct.pack('<QIB', count, h, 1))


class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        shared = Path(cls.build.name) / 'replay.so'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        str(ROOT / 'port/gdx_replay.c'), '-o', str(shared)], check=True)
        cls.lib = C.CDLL(str(shared))
        cls.lib.gdx_replay_open.argtypes = [C.c_int, C.c_char_p, C.c_char_p, C.c_char_p]
        cls.lib.gdx_replay_poll.argtypes = [C.POINTER(Pad), C.POINTER(C.c_ubyte), C.POINTER(C.c_uint)]

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name) / 'source.gdr'
        self.output = Path(self.tmp.name) / 'output.gdr'
        self.pads = (Pad * 4)()
        self.presence = (C.c_ubyte * 4)(1, 0, 1, 0)

    def tearDown(self):
        self.lib.gdx_replay_close(0)
        self.tmp.cleanup()

    def open(self, mode, identity=IDENTITY):
        return self.lib.gdx_replay_open(mode, str(self.source).encode(),
                                        str(self.output).encode(), identity.encode())

    def poll(self, i, final=False):
        return self.lib.gdx_replay_poll(self.pads, self.presence, (C.c_uint * 20)(*state(i, final)))

    def test_record_long_lossless_and_replay_injection(self):
        self.assertEqual(self.open(1), 1)
        expected = []
        for i in range(12000):
            self.assertEqual(self.lib.gdx_replay_service(), 1)
            self.pads[0] = Pad((0, 0x9030, 0x6000, 0xffff)[i % 4], (i % 256)-128, 127-(i % 256))
            self.presence[2] = i % 2
            expected.append((self.pads[0].buttons, self.pads[0].stickX, self.pads[0].stickY,
                             self.presence[2]))
            self.assertEqual(self.poll(i, i == 11999), 1)
        self.assertEqual(self.lib.gdx_replay_close(1), 1)
        self.output.rename(self.source)
        self.assertEqual(validate(self.source)['polls'], 12000)
        parsed = iter(records(self.source))
        first = next(parsed)
        self.assertEqual(first[1][0], (0, -128, 127, 1))
        second = next(parsed)
        self.assertEqual(second[1][0], (0x9030, -127, 126, 1))
        parsed.close()
        self.assertEqual(self.open(2), 1)
        for i, want in enumerate(expected):
            self.assertEqual(self.lib.gdx_replay_service(), 1)
            self.pads[0] = Pad(0xffff, 99, 99)  # live input must be overwritten
            self.assertEqual(self.poll(i, i == 11999), 1)
            self.assertEqual((self.pads[0].buttons, self.pads[0].stickX,
                              self.pads[0].stickY, self.presence[2]), want)
        self.assertEqual(self.lib.gdx_replay_service(), 1)
        self.assertEqual(self.poll(12000), 0)
        self.assertEqual(self.lib.gdx_replay_close(1), 1)
        self.assertEqual(self.source.read_bytes(), self.output.read_bytes())

    def test_overflow_fails_instead_of_dropping_poll(self):
        self.assertEqual(self.open(1), 1)
        self.assertEqual(self.poll(0), 1)
        self.assertEqual(self.poll(1), -1)

    def test_incomplete_recording(self):
        self.assertEqual(self.open(1), 1)
        self.poll(0)
        self.lib.gdx_replay_close(0)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate(self.output)

    def test_configuration_mismatch(self):
        write_fixture(self.source)
        self.assertEqual(self.open(2, 'b'*64), -1)

    def test_mutually_exclusive_open(self):
        self.assertEqual(self.open(1), 1)
        self.assertEqual(self.open(2), -1)

    def test_malformed_and_truncated_inputs(self):
        write_fixture(self.source)
        good = self.source.read_bytes()
        corruptions = [good[:20], b'BADMAGIC'+good[8:], good[:90], good[:-1], good[:-14],
                       good+b'trailing', good[:77]+b'\x02'+good[78:],
                       good[:-5]+b'\0'*5]
        for data in corruptions:
            with self.subTest(length=len(data)):
                self.source.write_bytes(data)
                with self.assertRaises((ValueError, UnicodeError)):
                    validate(self.source)
                result = self.open(2)
                if result == 1:
                    for i in range(20):
                        result = self.lib.gdx_replay_service()
                        if result < 0:
                            break
                        result = self.poll(i)
                        if result <= 0:
                            break
                    self.assertEqual(result, -1)
                self.lib.gdx_replay_close(0)

    def test_semantic_change_keeps_valid_candidate_checksum(self):
        write_fixture(self.source)
        self.assertEqual(self.open(2), 1)
        for i in range(9):
            self.assertEqual(self.lib.gdx_replay_service(), 1)
            s = state(i, i == 8)
            if i == 4:
                s[12] += 1
            self.assertEqual(self.lib.gdx_replay_poll(self.pads, self.presence,
                                                     (C.c_uint * 20)(*s)), 1)
        self.assertEqual(self.lib.gdx_replay_service(), 1)
        self.assertEqual(self.lib.gdx_replay_close(1), 1)
        result = compare(self.source, self.output)
        self.assertEqual((result['poll'], result['subsystem']), (4, 'lod'))


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a, self.b = (Path(self.tmp.name)/n for n in ('a.gdr', 'b.gdr'))
        write_fixture(self.a)

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_divergence(self):
        write_fixture(self.b, change=(4, 11))
        result = compare(self.a, self.b)
        self.assertEqual(result, {'match': False, 'poll': 4, 'tick': 1,
                                 'subsystem': 'energy_attack', 'reference': 48, 'candidate': 49})

    def test_match(self):
        write_fixture(self.b)
        self.assertTrue(compare(self.a, self.b)['match'])

    def test_matching_prefix_rejected(self):
        self.b.write_bytes(self.a.read_bytes()[:-14])
        report = compare(self.a, self.b)
        self.assertFalse(report['match'])
        self.assertEqual(report['subsystem'], 'endpoint')

    def test_early_footer_not_full_race(self):
        write_fixture(self.b, count=2)
        with self.assertRaisesRegex(ValueError, 'complete three-lap'):
            validate(self.b)

    def test_poll_boundaries_preserved(self):
        rows = list(records(self.a))
        self.assertEqual([r[2]['tick'] for r in rows], [0, 0, 0, 1, 1, 1, 2, 2, 2])
        self.assertEqual([r[1][0][0] for r in rows], [0, 0x8020, 0, 0x8020, 0, 0x8020, 0, 0x8020, 0])

    def test_metadata_identity_and_mismatch(self):
        metadata = {'schema': 1, 'content': 'synthetic host fixture only'}
        manifest = Path(self.tmp.name) / 'manifest.json'
        manifest.write_text(json.dumps({'metadata': metadata, 'identity': token(metadata)}))
        self.assertEqual(metadata_identity(manifest), token(metadata))
        manifest.write_text(json.dumps({'metadata': metadata, 'identity': 'b' * 64}))
        with self.assertRaisesRegex(ValueError, 'metadata identity'):
            metadata_identity(manifest)

    def test_cli_rejects_incomplete_and_reports_json(self):
        metadata = {'schema': 1}
        manifest = Path(self.tmp.name) / 'manifest.json'
        manifest.write_text(json.dumps({'metadata': metadata, 'identity': token(metadata)}))
        data = self.a.read_bytes()
        self.a.write_bytes(data[:8] + token(metadata).encode() + data[72:-14])
        report = Path(self.tmp.name) / 'report.json'
        result = subprocess.run(['python3', str(ROOT / 'tools/benchmark_3ds/replay.py'),
                                 str(self.a), '--report', str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('missing footer', json.loads(report.read_text())['error'])

    def test_divergence_reported_even_when_candidate_truncated(self):
        write_fixture(self.b, change=(2, 12))
        self.b.write_bytes(self.b.read_bytes()[:-14])
        report = compare(self.a, self.b)
        self.assertEqual((report['poll'], report['subsystem']), (2, 'lod'))
        self.assertIn('missing footer', report['completion_error'])
