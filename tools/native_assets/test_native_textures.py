import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import compile_textures as c


class Textures(unittest.TestCase):
    def test_i4_nibble_order_and_alpha(self):
        rgba = c.decode(bytes([0x0F, 0x18]) * 16, 'I4', 8, 8)
        self.assertEqual(rgba[:16], bytes([0]*4 + [255]*4 + [17]*4 + [136]*4))

    def test_ia4_three_bit_intensity_binary_alpha(self):
        rgba = c.decode(bytes([0x01, 0xEF]) * 16, 'IA4', 8, 8)
        self.assertEqual(rgba[:16], bytes([0,0,0,0, 0,0,0,255, 255,255,255,0, 255,255,255,255]))
        raw=bytes([0x02,0x46,0x8A,0xCE])*8
        self.assertEqual(list(c.decode(raw,'IA4',8,8)[::4])[:8], [0,36,73,109,146,182,219,255])

    def test_rgba5551_big_endian(self):
        raw = bytes.fromhex('F80107C1003FFFFE') * 16
        self.assertEqual(c.decode(raw, 'RGBA16', 8, 8)[:16],
                         bytes([255,0,0,255, 0,255,0,255, 0,0,255,255, 255,255,255,0]))

    def test_rgba5551_intermediate_expansion(self):
        self.assertEqual(c.decode(struct.pack('>H', (16<<11)|(1<<6)|(30<<1)|1)*64,
                                  'RGBA16',8,8)[:4], bytes([132,8,247,255]))

    def test_layout_known_offsets_bottom_up_abgr_and_tiles(self):
        # Explicit offsets independently tabulated from PICA x/y bit positions.
        linear = bytearray(16*16*4)
        points = [(0,0,170), (1,0,171), (0,1,168), (7,15,21),
                  (8,15,64), (0,8,42), (15,0,255)]
        for n, (x,y,_) in enumerate(points,1):
            linear[(y*16+x)*4:(y*16+x+1)*4] = bytes([n,2,3,4])
        tiled = c.pica_rgba8(linear,16,16)
        for n, (_,_,index) in enumerate(points,1):
            self.assertEqual(tiled[index*4:index*4+4],bytes([4,3,2,n]))
        self.assertEqual(sum(v != 0 for v in tiled),len(points)*4)

    def test_unsupported_and_truncated_inputs(self):
        for fmt, w, h, raw in [('CI4',8,8,b'\0'*32), ('I4',8,8,b''),
                               ('I4',4,8,b'\0'*16), ('I4',9,8,b'\0'*36),
                               ('I4',2048,8,b''), ('I4',True,8,b'')]:
            with self.subTest(fmt=fmt,w=w,h=h), self.assertRaises(ValueError):
                c.decode(raw,fmt,w,h)
        with self.assertRaises(ValueError): c.pica_rgba8(b'',8,8)
        with self.assertRaises(ValueError): c.compile_tiles(bytes(64))

    def test_finite_catalog_and_gpu_budget(self):
        entries,payload = c.compile_tiles(bytes(c.SOURCE_SIZE))
        self.assertEqual([e['tile'] for e in entries],list(range(8)))
        self.assertEqual(len(payload),18432)
        self.assertEqual(entries[0]['symbol'],'D_3004618')
        self.assertEqual(entries[2]['source_format'],'IA4')
        self.assertEqual(entries[7]['mode_t'],'wrap')

    def synthetic_bundle(self):
        segment=bytes(c.SOURCE_SIZE)
        return patch.object(c,'SOURCE_SHA256',c.digest(segment)),segment

    def test_deterministic_bundle_and_corruption(self):
        context,segment=self.synthetic_bundle()
        with context:
            bundle=c.make_bundle(segment)
            self.assertEqual(bundle,c.make_bundle(segment))
            self.assertEqual(len(c.validate_bundle(bundle)['textures']),8)
            for offset in (0,8,12,16,48,len(bundle)-1):
                bad=bytearray(bundle);bad[offset]^=1
                with self.subTest(offset=offset),self.assertRaises(ValueError):
                    c.validate_bundle(bad)
            for bad in (bundle[:10],bundle[:-1],bundle+b'\0',bytes(c.MAX_BUNDLE+1)):
                with self.assertRaises(ValueError): c.validate_bundle(bad)

    def test_catalog_rejection_after_checksum_recalculation(self):
        context,segment=self.synthetic_bundle()
        with context:
            bundle=c.make_bundle(segment)
            length=struct.unpack_from('<I',bundle,12)[0]
            metadata=json.loads(bundle[48:48+length]);payload=bundle[48+length:]
            for key,value in [('offset',4),('size',0),('tile',8),('mode_s','wrap'),('width',1024)]:
                with self.subTest(key=key):
                    changed=json.loads(json.dumps(metadata));changed['textures'][0][key]=value
                    raw=json.dumps(changed,sort_keys=True,separators=(',',':')).encode()
                    content=raw+payload
                    bad=struct.pack('<8sII',c.MAGIC,1,len(raw))+hashlib.sha256(content).digest()+content
                    with self.assertRaises(ValueError): c.validate_bundle(bad)
            metadata['version']=True
            raw=json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()
            content=raw+payload
            bad=struct.pack('<8sII',c.MAGIC,1,len(raw))+hashlib.sha256(content).digest()+content
            with self.assertRaises(ValueError):c.validate_bundle(bad)

    def test_wrong_source_identity(self):
        with self.assertRaises(ValueError): c.make_bundle(bytes(c.SOURCE_SIZE))

    def test_archive_bounds_header_identity_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'source.zip'
            for payload in (b'', bytes(68+c.SOURCE_SIZE)):
                with zipfile.ZipFile(archive,'w') as z:z.writestr('segment_blob/setup_gfx',payload)
                with self.assertRaises(ValueError):c.read_source(archive)
            header=bytearray(68);header[:12]=bytes.fromhex('00000000424c424f00000000')
            struct.pack_into('<I',header,64,c.SOURCE_SIZE)
            with zipfile.ZipFile(archive,'w') as z:z.writestr('segment_blob/setup_gfx',header+bytes(c.SOURCE_SIZE))
            with self.assertRaises(ValueError):c.read_source(archive)
            with patch.object(c,'SOURCE_SHA256',c.digest(bytes(c.SOURCE_SIZE))):
                self.assertEqual(c.read_source(archive),bytes(c.SOURCE_SIZE))
            # Corrupt the stored body without updating the ZIP CRC.
            stored=bytearray(archive.read_bytes())
            filename_length,extra_length=struct.unpack_from('<HH',stored,26)
            stored[30+filename_length+extra_length+68]^=1
            archive.write_bytes(stored)
            with self.assertRaises(zipfile.BadZipFile):c.read_source(archive)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(archive,'w') as z:
                    for _ in range(2):z.writestr('segment_blob/setup_gfx',header+bytes(c.SOURCE_SIZE))
            with self.assertRaises(ValueError):c.read_source(archive)

    def test_source_path_is_configurable(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'machine_draw.c'
            body='\n return gfx;'
            path.write_text('Gfx* Machine_DrawLoadBlueFalconTextures(Gfx* gfx) {'+body+'\n}')
            with self.assertRaises(ValueError):c.verify_recipe(path)
            with patch.object(c,'RECIPE_SHA256',c.digest(body.encode())):c.verify_recipe(path)


if __name__=='__main__':unittest.main()
