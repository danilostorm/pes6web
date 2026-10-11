import json
from pathlib import Path
import struct
import tempfile
import contextlib
import io
import unittest
from tools.inspect_psp import analyze, decode_sfo, elf_info, inspect_file, main


def make_sfo(title='Pro Evolution Soccer 6', disc_id='ULES00476'):
    entries = [('TITLE', title.encode()+b'\0', 0x0204), ('DISC_ID', disc_id.encode()+b'\0', 0x0204), ('DISC_VERSION', b'1.03\0', 0x0204)]
    names = b''; values = b''; records = b''
    for key, value, fmt in entries:
        records += struct.pack('<HHIII', len(names), fmt, len(value), len(value), len(values))
        names += key.encode()+b'\0'
        values += value
    return struct.pack('<5I', 0x46535000, 0x101, 20 + len(entries)*16, 20 + len(entries)*16 + len(names), len(entries))+records+names+values


class InspectorTests(unittest.TestCase):
    def test_sfo_fields(self):
        parsed = decode_sfo(make_sfo())
        self.assertEqual(parsed['DISC_ID'], 'ULES00476')
        self.assertEqual(parsed['TITLE'], 'Pro Evolution Soccer 6')

    def test_sfo_rejects_bad_counts(self):
        data = bytearray(make_sfo())
        struct.pack_into('<I', data, 16, 99999)
        with self.assertRaises(ValueError):
            decode_sfo(bytes(data))

    def test_sfo_rejects_offsets(self):
        data = bytearray(make_sfo())
        struct.pack_into('<I', data, 12, 1000000)
        with self.assertRaises(ValueError):
            decode_sfo(bytes(data))

    def test_elf_entry(self):
        raw=bytearray(52)
        raw[:6]=b'\x7fELF\x01\x01'
        struct.pack_into('<H',raw,18,8)
        struct.pack_into('<I',raw,24,0x08804000)
        self.assertEqual(elf_info(bytes(raw))['entry_point'], '0x08804000')

    def test_encrypted_and_zero_boot_detection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'PSP_GAME'
            (root/'SYSDIR').mkdir(parents=True)
            (root/'SYSDIR'/'EBOOT.BIN').write_bytes(b'~PSP'+ bytes(0xD0))
            (root/'SYSDIR'/'BOOT.BIN').write_bytes(bytes(1914))
            (root/'PARAM.SFO').write_bytes(make_sfo())
            result=analyze(Path(d))
            self.assertEqual(result['files']['EBOOT.BIN']['status'], 'encrypted_psp')
            self.assertEqual(result['files']['BOOT.BIN']['status'], 'zero_filled')
            self.assertFalse(result['ready_for_recompilation'])
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([d, '--json']),0)
            self.assertEqual(json.loads(output.getvalue())['platform'], 'PSP')

    def test_non_psp_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                analyze(Path(d))


if __name__ == '__main__':
    unittest.main()
