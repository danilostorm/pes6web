import struct
import tempfile
import unittest
from pathlib import Path
from tools.recover_native_entry import candidate, add_seed, add_fallthrough_range


def elf():
    b = bytearray(512)
    b[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<HH", b, 16, 2, 8)
    struct.pack_into("<I", b, 28, 52)
    struct.pack_into("<HH", b, 42, 32, 1)
    struct.pack_into("<IIIIIII", b, 52, 1, 128, 0x08810000, 0, 32, 64, 5)
    struct.pack_into("<I", b, 136, 0x00431021)
    return bytes(b)


class RecoverNativeEntryTests(unittest.TestCase):
    log = "[kernel] halted: Unsupported Allegrex instruction 0x00000000 at 0x08810008: invalid internal function entry\n"

    def test_executable_elf_entry(self):
        self.assertEqual(candidate(self.log, elf()), 0x08810008)

    def test_nonexecutable_mapping_rejected(self):
        modified = bytearray(elf())
        struct.pack_into("<I", modified, 52 + 24, 6)
        with self.assertRaises(ValueError):
            candidate(self.log, bytes(modified))

    def test_not_a_halt(self):
        with self.assertRaises(ValueError):
            candidate("[pspweb] ran 180 frames", elf())

    def test_zero_word_rejected(self):
        with self.assertRaises(ValueError):
            candidate(self.log.replace("0x08810008", "0x08810004"), elf())

    def test_range_enlargement_is_bounded_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "ranges.txt"
            self.assertTrue(add_fallthrough_range(f, 0x0886A7E8))
            self.assertFalse(add_fallthrough_range(f, 0x0886AA10))
            self.assertEqual(f.read_text().strip(), "0x08860000-0x08870000")
            with self.assertRaises(ValueError):
                add_fallthrough_range(f, 0x08880000, limit=1)

    def test_atomic_private_list_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "verified-extra-seeds.txt"
            self.assertTrue(add_seed(dest, 0x08810008))
            self.assertFalse(add_seed(dest, 0x08810008))
            self.assertEqual(dest.read_text().strip(), "0x08810008")
            with self.assertRaises(ValueError):
                add_seed(dest, 0x08810010, limit=1)


if __name__ == "__main__":
    unittest.main()
