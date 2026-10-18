import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest
import compile_textures as c


class MaterialScene(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();library=Path(cls.tmp.name)/'scene.so'
        subprocess.run(['cc','-std=c11','-shared','-fPIC','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined','-fno-sanitize-recover=undefined',
                        str(c.ROOT/'port/3ds/native/material_scene.c'),'-o',str(library)],check=True)
        cls.lib=ctypes.CDLL(str(library))
        cls.lib.material_scene_prepare.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p]
        cls.lib.material_scene_prepare.restype=ctypes.c_char_p
        # Source-audited ordered ranges, original primitive/environment endpoints.
        rows=[(0,12,1,0xffffffff,0xffa5630e,0),
              (12,42,2,0xff00ffff,0xffa5630e,1),
              (54,6,3,0xff00ffff,0xffa5630e,1),
              (60,6,4,0xffffffff,0xffa5630e,1),
              (66,156,5,0xffffffff,0xffa5630e,1),
              (222,12,6,0xffffffff,0xff000000,1),
              (234,24,7,0xffffffff,0xff000000,1),
              (258,30,0,0xffffeed1,0xffa5630e,1)]
        cls.source=(ctypes.c_uint32*64)(*(value for row in rows for value in (*row,1,0)))

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_original_order_counts_colors_and_explicit_stock_livery(self):
        output=(ctypes.c_uint32*64)()
        self.assertIsNone(self.lib.material_scene_prepare(self.source,8,output))
        self.assertEqual([output[8*i+2] for i in range(8)],[1,2,3,4,5,6,7,0])
        self.assertEqual(sum(output[8*i+1] for i in range(8)),288)
        for i in range(8):
            for field in (0,1,2,3,5,6,7):self.assertEqual(output[8*i+field],self.source[8*i+field])
            self.assertEqual(output[8*i+4],0xffff0000 if i<5 else self.source[8*i+4])
        self.assertEqual(self.source[4],0xffa5630e) # borrowed v1 source unchanged

    def test_every_recipe_field_mutation_fails_and_zeroes_output(self):
        for index in range(64):
            changed=(ctypes.c_uint32*64)(*self.source);changed[index]^=1
            output=(ctypes.c_uint32*64)(*([0xffffffff]*64))
            self.assertIsNotNone(self.lib.material_scene_prepare(changed,8,output),index)
            self.assertEqual(list(output),[0]*64,index)

    def test_unsupported_count_and_null(self):
        output=(ctypes.c_uint32*64)()
        for count in (0,7,9,64):self.assertIsNotNone(self.lib.material_scene_prepare(self.source,count,output))
        self.assertIsNotNone(self.lib.material_scene_prepare(None,8,output))
        self.assertIsNotNone(self.lib.material_scene_prepare(self.source,8,None))


if __name__=='__main__':unittest.main()
