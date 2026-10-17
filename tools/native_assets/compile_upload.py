#!/usr/bin/env python3
"""Convert the validated M1b host bundle to fixed native swatch format."""
import argparse
from pathlib import Path
import struct
import tempfile
import zlib
import compile_textures as c

MAGIC=b'GDXSWCH\0'
HEADER=128
ENTRY=struct.Struct('<12I')


def make_pack(bundle):
    manifest=c.validate_bundle(bundle)
    metadata_size=struct.unpack_from('<I',bundle,12)[0]
    payload=bundle[48+metadata_size:]
    start=HEADER+8*ENTRY.size
    header=bytearray(HEADER)
    struct.pack_into('<8s6I',header,0,MAGIC,1,start+len(payload),8,HEADER,start,0)
    header[32:64]=bytes.fromhex(c.SOURCE_SHA256)
    header[64:96]=bytes.fromhex(c.RECIPE_SHA256)
    entries=[]
    for t in manifest['textures']:
        entries.append(ENTRY.pack(t['tile'],t['width'],t['height'],
                                  {'I4':1,'IA4':2,'RGBA16':3}[t['source_format']],
                                  start+t['offset'],t['size'],
                                  {'wrap':0,'mirror_clamp':1}[t['mode_s']],
                                  {'wrap':0,'mirror_clamp':1}[t['mode_t']],
                                  t['mask_s'],t['mask_t'],t['shift_s'],t['shift_t']))
    pack=header+b''.join(entries)+payload
    struct.pack_into('<I',pack,28,zlib.crc32(pack))
    return bytes(pack)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',required=True,type=Path)
    parser.add_argument('--out',type=Path,default=c.ROOT/'dist/native/sdmc/3ds/gdiffuser-native-swatch/textures.gdns')
    args=parser.parse_args()
    try:
        # Bound input before read, independently of the bundle validator.
        with args.bundle.open('rb') as f:
            bundle=f.read(c.MAX_BUNDLE+1)
        pack=make_pack(bundle)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=args.out.parent,prefix=args.out.name+'.',delete=False) as f:
            temp=Path(f.name)
            try:
                f.write(pack);f.close();temp.replace(args.out)
            finally:temp.unlink(missing_ok=True)
        print(f'{args.out}: {len(pack)} bytes sha256={c.digest(pack)}')
    except (OSError,ValueError,struct.error) as e:parser.exit(1,f'native swatch compiler: {e}\n')


if __name__=='__main__':main()
