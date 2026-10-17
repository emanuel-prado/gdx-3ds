#!/usr/bin/env python3
"""Compile the USA rev0 Blue Falcon LOD2 recipe; no runtime GBI dependency.
Input is the existing prebake archive. Output is private game-derived data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ROM_SHA1 = '5f658e88ffa9de23cba6986a8fd3d3a90d7b4340'
SEG_SHA256 = 'f19a962ab79e3edb5e31266a5f1137710ae31eaebf2d871b865652064c638194'
HEADER = 192
VERTEX = struct.Struct('<7f4B2h')
MATERIAL = struct.Struct('<8I')
MAX_PACK = 1024 * 1024


def read_segment(archive):
    with zipfile.ZipFile(archive) as z:
        name = 'segment_blob/machine_global_gfx'
        if z.namelist().count(name) != 1:
            raise ValueError('missing or duplicate machine segment')
        info = z.getinfo(name)
        if info.file_size != 68 + 0x48CB0:
            raise ValueError('invalid source resource size')
        b = z.read(name)  # zip CRC verified by zipfile
    if b[:12] != bytes.fromhex('00000000424c424f00000000') or struct.unpack_from('<I', b, 64)[0] != len(b)-68:
        raise ValueError('unsupported Torch BLOB header')
    segment = b[68:]
    if hashlib.sha256(segment).hexdigest() != SEG_SHA256:
        raise ValueError('source is not the supported USA rev0 machine segment')
    return segment


def recipe(text):
    match = re.search(r'Gfx\* Machine_DrawBlueFalconLod2\(Gfx\* gfx\) \{(.*?)\n\}', text, re.S)
    if not match:
        raise ValueError('missing Blue Falcon LOD2 recipe')
    body = match[1]
    calls = re.findall(r'(g\w+)\((.*?)\);', body, re.S)
    remainder = re.sub(r'g\w+\(.*?\);', '', body, flags=re.S).replace('return gfx;', '')
    if remainder.strip():
        raise ValueError('unsupported control flow in machine recipe')
    return body, calls


def compile_mesh(segment, text):
    body, calls = recipe(text)
    vertices, indices, materials = [], [], []
    cache, dedup = {}, {}
    prim, env, tile, combine = (255,255,255,255), (14,99,165,255), None, None
    state = None
    for op, args in calls:
        a = [v.strip() for v in args.split(',')]
        if a.pop(0) != 'gfx++':
            raise ValueError('unsupported recipe destination')
        if op == 'gDPPipeSync' and not a:
            continue
        if op in ('gDPSetPrimColor', 'gDPSetEnvColor'):
            if op == 'gDPSetPrimColor':
                if a[:2] != ['0','0']:
                    raise ValueError('unsupported primitive parameters')
                a = a[2:]
            color = tuple(map(int, a))
            if len(color) != 4 or any(not 0 <= n <= 255 for n in color):
                raise ValueError('invalid color')
            if op == 'gDPSetPrimColor': prim = color
            else: env = color
        elif op == 'gDPSetCombineLERP':
            known = [
                'TEXEL0 ENVIRONMENT TEXEL0_ALPHA ENVIRONMENT 0 0 0 ENVIRONMENT COMBINED 0 SHADE 0 0 0 0 COMBINED',
                'PRIMITIVE ENVIRONMENT TEXEL0 ENVIRONMENT 0 0 0 ENVIRONMENT COMBINED 0 SHADE 0 0 0 0 COMBINED']
            try: combine = known.index(' '.join(a))
            except ValueError: raise ValueError('unsupported material combiner') from None
        elif op == 'gSPTexture':
            if len(a) != 5 or a[:3] != ['0xFFFF','0xFFFF','0'] or a[4] != 'G_ON':
                raise ValueError('unsupported texture state')
            tile = int(a[3])
            if not 0 <= tile <= 7: raise ValueError('invalid tile')
        elif op == 'gSPVertex':
            if len(a) != 3: raise ValueError('invalid vertex arguments')
            m = re.fullmatch(r'&?D_7([0-9A-Fa-f]{6})(?:\[(\d+)\])?', a[0])
            if not m or len(a) != 3 or a[2] != '0':
                raise ValueError('unsupported vertex load')
            offset = int(m[1],16) + int(m[2] or 0)*16
            count = int(a[1])
            if not 1 <= count <= 64 or offset + count*16 > len(segment):
                raise ValueError('vertex load outside source')
            cache = {i: (offset+i*16, segment[offset+i*16:offset+(i+1)*16]) for i in range(count)}
        elif op in ('gSP1Triangle', 'gSP2Triangles'):
            n = list(map(int,a))
            if len(n) != (4 if op == 'gSP1Triangle' else 8) or any(n[j] for j in range(3,len(n),4)):
                raise ValueError('unsupported triangle flags')
            if tile is None or combine is None: raise ValueError('missing material')
            current = (tile,prim,env,combine)
            if state != current:
                materials.append([len(indices),0,tile,int.from_bytes(bytes(prim),'little'),int.from_bytes(bytes(env),'little'),combine,1,0])
                state = current
            # Explicit M1a approximation: unlit solid material, no texture sampling.
            color = env if combine == 0 else prim
            for j in range(0,len(n),4):
                for idx in n[j:j+3]:
                    if idx not in cache: raise ValueError('triangle references unloaded vertex')
                    address, raw = cache[idx]
                    key = (address,current)
                    if key not in dedup:
                        x,y,z,flag,u,v,nx,ny,nz,alpha = struct.unpack('>hhhHhh4B',raw)
                        if flag: raise ValueError('unsupported vertex flag')
                        dedup[key] = len(vertices)
                        vertices.append(VERTEX.pack(x,y,z,*(c/255 for c in color),nx,ny,nz,alpha,u,v))
                    indices.append(dedup[key])
                    materials[-1][1] += 1
        else:
            raise ValueError('unsupported recipe operation: '+op)
    if not vertices or len(vertices)>4096 or not indices or len(indices)>24576 or len(materials)>64:
        raise ValueError('mesh exceeds M1a budget or is empty')
    return vertices,indices,materials,body


def make_pack(segment, text):
    vertices,indices,materials,body = compile_mesh(segment,text)
    vo = HEADER
    io = vo + len(vertices)*VERTEX.size
    mo = (io + len(indices)*2 + 3) & ~3
    payload = b''.join(vertices)+struct.pack('<%dH'%len(indices),*indices)+bytes(mo-io-len(indices)*2)+b''.join(MATERIAL.pack(*m) for m in materials)
    positions = [struct.unpack_from('<3f',v) for v in vertices]
    bounds = [min(p[i] for p in positions) for i in range(3)]+[max(p[i] for p in positions) for i in range(3)]
    header = struct.pack('<8s10I',b'GDXM1A\0\0',1,HEADER+len(payload),len(vertices),len(indices),len(materials),vo,io,mo,0,1)
    header += bytes.fromhex(ROM_SHA1)+hashlib.sha256(segment).digest()+hashlib.sha256(body.encode()).digest()+hashlib.sha256(Path(__file__).read_bytes()).digest()+struct.pack('<6fI',*bounds,0)
    pack = bytearray(header+payload)
    struct.pack_into('<I',pack,40,zlib.crc32(pack))
    return bytes(pack)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--out',type=Path,default=ROOT/'dist/native/sdmc/3ds/gdiffuser-native/machine.gdnp')
    a=p.parse_args()
    try:
        pack=make_pack(read_segment(a.archive),(ROOT/'decomp/src/overlays/ovl_i9/machine_draw.c').read_text())
        a.out.parent.mkdir(parents=True,exist_ok=True)
        tmp=a.out.with_suffix('.tmp'); tmp.write_bytes(pack); tmp.replace(a.out)
        print(json.dumps({'path':str(a.out),'sha256':hashlib.sha256(pack).hexdigest(),'bytes':len(pack),'vertices_indices_materials':struct.unpack_from('<3I',pack,16)}))
    except (OSError,ValueError,zipfile.BadZipFile,struct.error) as e:
        p.exit(1,f'native compiler: {e}\n')

if __name__=='__main__': main()
