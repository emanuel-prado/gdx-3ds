#!/usr/bin/env python3
"""Compile the finite USA rev0 Blue Falcon tile catalog for native M1b.

Host-only experimental bundle; deliberately independent of the M1a mesh format.
No generated game data belongs in Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA256 = 'f654cebe506385d9bb3ce8664cbf6dcd96593c6600f3e8486c31a019b3a96934'
RECIPE_SHA256 = 'e5845153f9dbca29d7fff4890e455fa90173438070d1db074186cd2a75fae334'
SOURCE_SIZE = 0x3D370
MAX_BUNDLE = 128 * 1024
MAGIC = b'GDXM1BT\0'
# (stable tile ID, source symbol, segment-3 offset, format, width, height,
#  N64 S mode, N64 T mode, S mask bits, T mask bits). No texture has shifts.
# Tile 0 is loaded by setup DL D_303A6A8, not the machine texture loader.
CATALOG = (
    (0, 'D_3004618', 0x4618, 'I4', 16, 16, 'mirror_clamp', 'mirror_clamp', 4, 4),
    (1, 'aDecalBlueFalconWingCheckeredTex', 0x4918, 'RGBA16', 16, 16, 'mirror_clamp', 'wrap', 4, 4),
    (2, 'aDecalStripeTex', 0x4698, 'IA4', 16, 16, 'mirror_clamp', 'wrap', 4, 4),
    (3, 'aDecalBlueFalconArrowTex', 0x4598, 'I4', 16, 16, 'mirror_clamp', 'mirror_clamp', 4, 4),
    (4, 'aLogoBlueFalconTex', 0x4718, 'I4', 64, 16, 'mirror_clamp', 'mirror_clamp', 6, 4),
    (5, 'aMachineNumber7Tex', 0x4498, 'I4', 16, 32, 'mirror_clamp', 'mirror_clamp', 4, 5),
    (6, 'aRearDuctTex', 0x4D18, 'I4', 32, 32, 'mirror_clamp', 'mirror_clamp', 5, 5),
    (7, 'aBooster1Tex', 0x4B18, 'I4', 32, 32, 'mirror_clamp', 'wrap', 5, 5),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_source(archive):
    """Read bounded, CRC-checked Torch blob; verify the entire source segment."""
    with zipfile.ZipFile(archive) as z:
        name = 'segment_blob/setup_gfx'
        if z.namelist().count(name) != 1:
            raise ValueError('missing or duplicate setup segment')
        if z.getinfo(name).file_size != 68 + SOURCE_SIZE:
            raise ValueError('invalid setup resource size')
        blob = z.read(name)
    if (blob[:12] != bytes.fromhex('00000000424c424f00000000') or
            struct.unpack_from('<I', blob, 64)[0] != SOURCE_SIZE):
        raise ValueError('unsupported Torch BLOB header')
    segment = blob[68:]
    if digest(segment) != SOURCE_SHA256:
        raise ValueError('setup segment is not supported USA rev0')
    return segment


def verify_recipe(source_path):
    text = Path(source_path).read_text()
    match = re.search(r'Gfx\* Machine_DrawLoadBlueFalconTextures\(Gfx\* gfx\) \{(.*?)\n\}', text, re.S)
    if not match or digest(match[1].encode()) != RECIPE_SHA256:
        raise ValueError('unsupported Blue Falcon texture loader recipe')


def dimensions(width, height):
    if (type(width) is not int or type(height) is not int or
            width < 8 or height < 8 or width > 1024 or height > 1024 or
            width & (width - 1) or height & (height - 1)):
        raise ValueError('texture dimensions must be powers of two in 8..1024')


def decode(raw, fmt, width, height):
    """Original packed, top-to-bottom texels -> linear RGBA bytes.

    I4 carries intensity in alpha too. IA4 is 3 intensity bits + one alpha bit.
    RDP bit replication preserves the full range (the legacy importer rounds
    differently). See paraLLEl-RDP shaders/texture.h convert_rgba16/sample_texel_ia4.
    """
    dimensions(width, height)
    if fmt not in ('RGBA16', 'I4', 'IA4'):
        raise ValueError('unsupported source texture format')
    count = width * height
    expected = count * 2 if fmt == 'RGBA16' else count // 2
    if len(raw) != expected:
        raise ValueError('source texture length mismatch')
    out = bytearray()
    for i in range(count):
        if fmt == 'RGBA16':
            n = int.from_bytes(raw[i*2:i*2+2], 'big')
            channels = ((n >> 11), (n >> 6) & 31, (n >> 1) & 31)
            rgba = tuple((v << 3) | (v >> 2) for v in channels) + ((n & 1) * 255,)
        else:
            n = (raw[i//2] >> (4 if i % 2 == 0 else 0)) & 15
            intensity = n >> 1
            v = n * 17 if fmt == 'I4' else ((intensity << 5) | (intensity << 2) | (intensity >> 1))
            rgba = (v, v, v, v if fmt == 'I4' else (n & 1) * 255)
        out.extend(rgba)
    return bytes(out)


def pica_rgba8(rgba, width, height):
    """Bottom-up 8x8 Morton tiles; GPU_RGBA8 texel bytes are A, B, G, R.

    Matches gfx_citro3d.cpp UploadTexture's verified storage convention.
    """
    dimensions(width, height)
    if len(rgba) != width * height * 4:
        raise ValueError('linear texture length mismatch')
    out = bytearray(len(rgba))
    for y in range(height):
        dy = height - 1 - y
        for x in range(width):
            morton = sum((((x >> bit) & 1) << (bit*2)) |
                         (((dy >> bit) & 1) << (bit*2+1)) for bit in range(3))
            dst = (((dy//8)*(width//8) + x//8)*64 + morton)*4
            src = (y*width + x)*4
            out[dst:dst+4] = rgba[src:src+4][::-1]
    return bytes(out)


def compile_tiles(segment):
    """Compile only the declared catalog; caller handles source provenance."""
    textures, payload = [], bytearray()
    for tile, symbol, offset, fmt, width, height, s, t, mask_s, mask_t in CATALOG:
        size = width*height*2 if fmt == 'RGBA16' else width*height//2
        if offset < 0 or offset + size > len(segment):
            raise ValueError('texture outside source segment: ' + symbol)
        raw = segment[offset:offset+size]
        data = pica_rgba8(decode(raw, fmt, width, height), width, height)
        textures.append(dict(tile=tile, symbol=symbol, source_offset=offset,
                             source_format=fmt, width=width, height=height,
                             mode_s=s, mode_t=t, mask_s=mask_s, mask_t=mask_t,
                             shift_s=0, shift_t=0, offset=len(payload), size=len(data),
                             source_sha256=digest(raw), sha256=digest(data)))
        payload.extend(data)
    return textures, bytes(payload)


def make_bundle(segment):
    if len(segment) != SOURCE_SIZE or digest(segment) != SOURCE_SHA256:
        raise ValueError('unsupported source identity')
    textures, payload = compile_tiles(segment)
    manifest = dict(version=1, source_sha256=SOURCE_SHA256,
                    recipe_sha256=RECIPE_SHA256,
                    layout='pica_rgba8_abgr_bottom_up_morton8',
                    textures=textures, payload_sha256=digest(payload))
    metadata = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode('ascii')
    content = metadata + payload
    bundle = struct.pack('<8sII', MAGIC, 1, len(metadata)) + hashlib.sha256(content).digest() + content
    if len(bundle) > MAX_BUNDLE:
        raise ValueError('texture bundle exceeds budget')
    return bundle


def validate_bundle(bundle):
    """Host structural/integrity validator; not a future native loader."""
    if not 48 <= len(bundle) <= MAX_BUNDLE:
        raise ValueError('texture bundle size outside budget')
    magic, version, size = struct.unpack_from('<8sII', bundle)
    if magic != MAGIC or version != 1 or not 0 < size <= 8192 or 48+size > len(bundle):
        raise ValueError('unsupported texture bundle header')
    if hashlib.sha256(bundle[48:]).digest() != bundle[16:48]:
        raise ValueError('texture bundle checksum mismatch')
    try:
        m = json.loads(bundle[48:48+size])
    except (ValueError, UnicodeError) as e:
        raise ValueError('invalid texture metadata') from e
    if json.dumps(m, sort_keys=True, separators=(',', ':')).encode('ascii') != bundle[48:48+size]:
        raise ValueError('noncanonical texture metadata')
    payload = bundle[48+size:]
    if not isinstance(m, dict) or set(m) != {'version', 'source_sha256', 'recipe_sha256', 'layout', 'textures', 'payload_sha256'}:
        raise ValueError('invalid texture metadata fields')
    if (type(m['version']) is not int or m['version'] != 1 or m['source_sha256'] != SOURCE_SHA256 or
            m['recipe_sha256'] != RECIPE_SHA256 or
            m['layout'] != 'pica_rgba8_abgr_bottom_up_morton8' or
            m['payload_sha256'] != digest(payload) or not isinstance(m['textures'], list) or len(m['textures']) != 8):
        raise ValueError('invalid texture identity or payload')
    offset = 0
    for entry, catalog in zip(m['textures'], CATALOG):
        tile, symbol, src, fmt, w, h, s, t, ms, mt = catalog
        expected = dict(tile=tile, symbol=symbol, source_offset=src, source_format=fmt,
                        width=w, height=h, mode_s=s, mode_t=t, mask_s=ms, mask_t=mt,
                        shift_s=0, shift_t=0, offset=offset, size=w*h*4)
        if (not isinstance(entry, dict) or set(entry) != set(expected) | {'sha256', 'source_sha256'} or
                any(type(entry[k]) is not type(v) or entry[k] != v for k, v in expected.items()) or
                not isinstance(entry['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', entry['source_sha256']) or
                entry['sha256'] != digest(payload[offset:offset+w*h*4])):
            raise ValueError('invalid tile catalog, range or checksum')
        offset += w*h*4
    if offset != len(payload):
        raise ValueError('noncanonical texture payload size')
    return m


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT/'decomp/src/overlays/ovl_i9/machine_draw.c',
                        help='pinned machine_draw.c (configurable for separate worktrees)')
    parser.add_argument('--out', type=Path, default=ROOT/'dist/native/sdmc/3ds/gdiffuser-native/blue-falcon-textures.gdnt')
    args = parser.parse_args()
    try:
        verify_recipe(args.source)
        bundle = make_bundle(read_source(args.archive))
        manifest = validate_bundle(bundle)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # Unique sibling temp keeps parallel host invocations from sharing a temp file.
        import tempfile
        with tempfile.NamedTemporaryFile(dir=args.out.parent, prefix=args.out.name+'.', delete=False) as f:
            temp = Path(f.name)
            try:
                f.write(bundle)
                f.close()
                temp.replace(args.out)
            finally:
                temp.unlink(missing_ok=True)
        print(json.dumps(dict(path=str(args.out), sha256=digest(bundle), bytes=len(bundle),
                              textures=len(manifest['textures']), gpu_bytes=sum(t['size'] for t in manifest['textures']))))
    except (OSError, ValueError, zipfile.BadZipFile, struct.error) as e:
        parser.exit(1, f'native texture compiler: {e}\n')


if __name__ == '__main__':
    main()
