import ctypes
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zipfile
import zlib

import compile_machine as c

RECIPE = '''Gfx* Machine_DrawBlueFalconLod2(Gfx* gfx) {
    gDPSetCombineLERP(gfx++, PRIMITIVE, ENVIRONMENT, TEXEL0, ENVIRONMENT, 0, 0, 0, ENVIRONMENT, COMBINED, 0, SHADE, 0, 0, 0, 0, COMBINED);
    gSPTexture(gfx++, 0xFFFF, 0xFFFF, 0, 2, G_ON);
    gSPVertex(gfx++, D_7000000, 4, 0);
    gSP2Triangles(gfx++, 0, 1, 2, 0, 0, 2, 3, 0);
    return gfx;
}'''


class Assets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        lib=Path(cls.tmp.name)/'pack.so'
        subprocess.run(['cc','-std=c11','-shared','-fPIC','-Wall','-Wextra','-Werror','-fsanitize=undefined',
                        str(c.ROOT/'port/3ds/native/pack.c'),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib))
        cls.lib.native_pack_validate.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p]
        cls.lib.native_pack_validate.restype=ctypes.c_char_p
        cls.segment=b''.join(struct.pack('>hhhHhh4B',*p,0,32,-64,127,0,0,255) for p in [(0,0,0),(10,0,0),(0,10,0),(0,0,10)])

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def pack(self): return c.make_pack(self.segment,RECIPE)

    def validate(self,b):
        buf=ctypes.create_string_buffer(bytes(b))
        out=ctypes.create_string_buffer(128)
        return self.lib.native_pack_validate(buf,len(b),out)

    def mutate(self,offset,fmt,value):
        b=bytearray(self.pack());struct.pack_into(fmt,b,offset,value)
        struct.pack_into('<I',b,40,0);struct.pack_into('<I',b,40,zlib.crc32(b))
        return b

    def test_deterministic_and_load(self):
        self.assertEqual(self.pack(),self.pack());self.assertIsNone(self.validate(self.pack()))

    def test_original_coordinates_normals_uv_winding(self):
        p=self.pack();self.assertEqual(struct.unpack_from('<3f',p,192+36),(10,0,0))
        self.assertEqual(struct.unpack_from('<4B2h',p,192+28),(127,0,0,255,32,-64))
        self.assertEqual(struct.unpack_from('<6H',p,192+4*36),(0,1,2,0,2,3))

    def test_truncations_and_trailing_data(self):
        b=self.pack()
        for n in range(len(b)): self.assertIsNotNone(self.validate(b[:n]),n)
        self.assertIsNotNone(self.validate(b+b'\0'))

    def test_every_byte_corruption(self):
        b=self.pack()
        for i in range(len(b)):
            bad=bytearray(b);bad[i]^=0x80
            self.assertIsNotNone(self.validate(bad),i)

    def test_counts_offsets_and_version(self):
        for offset,value in [(8,2),(16,0),(16,0xffffffff),(20,24579),(24,65),(28,196),(32,0xffffffff),(36,0),(44,0),(188,1)]:
            self.assertIsNotNone(self.validate(self.mutate(offset,'<I',value)),(offset,value))

    def test_index_out_of_bounds(self):
        self.assertEqual(self.validate(self.mutate(192+4*36,'<H',4)),b'index reference')

    def test_material_rejection(self):
        mo=struct.unpack_from('<I',self.pack(),36)[0]
        for off,value in [(0,3),(4,999),(4,3),(8,8),(20,2),(24,0),(28,1)]:
            self.assertIsNotNone(self.validate(self.mutate(mo+off,'<I',value)))

    def test_nonfinite_positions_colors_bounds(self):
        for off in [192,192+12,164]:
            for n in [float('nan'),float('inf'),-float('inf')]:
                self.assertIsNotNone(self.validate(self.mutate(off,'<f',n)))
        self.assertIsNotNone(self.validate(self.mutate(192,'<f',20)))
        self.assertIsNotNone(self.validate(self.mutate(192+12,'<f',1.1)))

    def test_source_bounds_and_unloaded_vertices(self):
        for source in [self.segment[:16],b'']:
            with self.assertRaises(ValueError): c.make_pack(source,RECIPE)
        with self.assertRaises(ValueError): c.make_pack(self.segment,RECIPE.replace('0, 2, 3, 0','0, 2, 4, 0'))

    def test_unknown_recipe_and_control_flow(self):
        for s in [RECIPE.replace('return gfx;','if (1) return gfx;'),RECIPE.replace('gSPTexture','gUnknown'),RECIPE.replace('PRIMITIVE','UNKNOWN'),RECIPE.replace('G_ON','G_OFF')]:
            with self.assertRaises(ValueError): c.make_pack(self.segment,s)

    def test_single_triangle_alignment(self):
        recipe=RECIPE.replace('gSP2Triangles(gfx++, 0, 1, 2, 0, 0, 2, 3, 0)', 'gSP1Triangle(gfx++, 0, 1, 2, 0)')
        b=c.make_pack(self.segment,recipe)
        self.assertIsNone(self.validate(b))
        self.assertEqual(struct.unpack_from('<I',b,36)[0]%4,0)

    def test_invalid_archive(self):
        p=Path(self.tmp.name)/'bad.o2r';p.write_bytes(b'no')
        with self.assertRaises(zipfile.BadZipFile):c.read_segment(p)
        with zipfile.ZipFile(p,'w') as z:z.writestr('segment_blob/machine_global_gfx',b'no')
        with self.assertRaises(ValueError):c.read_segment(p)

    def test_wrong_source_identity(self):
        p=Path(self.tmp.name)/'wrong.o2r'
        b=bytearray(68+0x48cb0);b[:12]=bytes.fromhex('00000000424c424f00000000');struct.pack_into('<I',b,64,0x48cb0)
        with zipfile.ZipFile(p,'w') as z:z.writestr('segment_blob/machine_global_gfx',b)
        with self.assertRaisesRegex(ValueError,'supported USA'):c.read_segment(p)

if __name__=='__main__':unittest.main()
