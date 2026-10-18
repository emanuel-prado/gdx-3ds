import ctypes
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib
import compile_textures as c
import compile_upload as upload


class Upload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        library=Path(cls.tmp.name)/'texture_pack.so'
        subprocess.run(['cc','-std=c11','-shared','-fPIC','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined','-fno-sanitize-recover=undefined',
                        str(c.ROOT/'port/3ds/native/texture_pack.c'),'-o',str(library)],check=True)
        cls.lib=ctypes.CDLL(str(library))
        cls.lib.swatch_pack_validate.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p]
        cls.lib.swatch_pack_validate.restype=ctypes.c_char_p
        # Synthetic payload, never a game fixture. Fixed identity is metadata,
        # not authentication. The native loader validates layout and integrity.
        segment=bytes(c.SOURCE_SIZE);synthetic=c.digest(segment)
        with patch.object(c,'SOURCE_SHA256',synthetic):bundle=c.make_bundle(segment)
        content=bundle[48:].replace(synthetic.encode(),c.SOURCE_SHA256.encode())
        cls.bundle=bundle[:16]+hashlib.sha256(content).digest()+content
        cls.pack=upload.make_pack(cls.bundle)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def validate(self,pack):
        output=ctypes.create_string_buffer(b'\xa5'*1024)
        data=ctypes.create_string_buffer(bytes(pack))
        result=self.lib.swatch_pack_validate(data,len(pack),output)
        return result,output.raw

    def test_valid_deterministic_fixed_layout(self):
        self.assertEqual(self.pack,upload.make_pack(self.bundle))
        self.assertEqual(len(self.pack),18944)
        self.assertIsNone(self.validate(self.pack)[0])
        for i in range(8):
            tile,width,height,fmt,offset,size,*_=struct.unpack_from('<12I',self.pack,128+i*48)
            self.assertEqual(tile,i);self.assertEqual(size,width*height*4)
            self.assertEqual(self.pack[offset:offset+size],bytes(size))

    def test_corruption_checks_header_entries_and_payload(self):
        for offset in list(range(512))+list(range(512,len(self.pack),257)):
            bad=bytearray(self.pack);bad[offset]^=1
            error,output=self.validate(bad)
            self.assertIsNotNone(error,offset)
            self.assertEqual(output[:64],bytes(64),offset)

    def test_recalculated_crc_catalog_and_identity_rejection(self):
        for offset,value in [(8,2),(12,1),(16,9),(20,132),(24,0),
                             (32,0),(64,0),(96,1)]+[(128+i*48+j,0xffffffff) for i in range(8) for j in range(0,48,4)]:
            bad=bytearray(self.pack);struct.pack_into('<I',bad,offset,value)
            struct.pack_into('<I',bad,28,0);struct.pack_into('<I',bad,28,zlib.crc32(bad))
            self.assertIsNotNone(self.validate(bad)[0],offset)

    def test_truncations_excess_unaligned_and_null(self):
        for bad in (b'',self.pack[:127],self.pack[:511],self.pack[:-1],self.pack+b'\0'):
            self.assertIsNotNone(self.validate(bad)[0])
        data=ctypes.create_string_buffer(b'\0'+self.pack);output=ctypes.create_string_buffer(1024)
        self.assertIsNone(self.lib.swatch_pack_validate(ctypes.byref(data,1),len(self.pack),output))
        self.assertIsNotNone(self.lib.swatch_pack_validate(None,len(self.pack),output))
        self.assertIsNotNone(self.lib.swatch_pack_validate(data,len(self.pack),None))

    def test_bad_host_bundle_rejected(self):
        for bad in (b'',self.bundle[:-1],self.bundle+b'\0'):
            with self.assertRaises(ValueError):upload.make_pack(bad)


if __name__=='__main__':unittest.main()
