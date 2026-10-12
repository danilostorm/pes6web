import struct
import tempfile
from pathlib import Path
import unittest

from tools.diagnose_pc import address_info, generated_mentions, inspect, parse_load_segments


def make_elf(etype=2):
    data = bytearray(256)
    data[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<HH", data, 16, etype, 8)
    struct.pack_into("<I", data, 28, 52)
    struct.pack_into("<HH", data, 42, 32, 1)
    struct.pack_into("<IIIIII", data, 52, 1, 128, 0x0897FD00 if etype == 2 else 0, 0, 32, 64)
    for i in range(8):
        struct.pack_into("<I", data, 128 + i * 4, i + 101)
    return bytes(data)


class PcDiagnosticsTests(unittest.TestCase):
    def test_maps_elf_and_bss(self):
        blob = make_elf()
        self.assertEqual(address_info(blob, 0x0897FD08)["elf_file_offset"], "0x88")
        self.assertEqual(address_info(blob, 0x0897FD08)["words"][2], ("0x0897FD08", "0x00000067"))
        self.assertFalse(address_info(blob, 0x0897FD28)["in_file"])
        self.assertFalse(address_info(blob, 0x0897FE00)["mapped"])

    def test_prx_offset(self):
        blob = make_elf(0xFFA0)
        self.assertEqual(address_info(blob, 0x08804008)["elf_file_offset"], "0x88")

    def test_rejects_corrupt_headers(self):
        with self.assertRaises(ValueError):
            parse_load_segments(b"not a valid elf")
        broken = bytearray(make_elf())
        struct.pack_into("<H", broken, 44, 200)
        with self.assertRaises(ValueError):
            parse_load_segments(bytes(broken))

    def test_generated_scan_does_not_disclose_source(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "generated_unit_0001.cpp").write_text(
                "L_0897FD08: secret proprietary code\n"
            )
            self.assertEqual(generated_mentions(folder, 0x0897FD08), [
                ("generated_unit_0001.cpp", 1, "label")
            ])
            path = folder / "test.elf"
            path.write_bytes(make_elf())
            report = inspect(path, folder, [0x0897FD08])
            self.assertNotIn("secret proprietary code", report)
            self.assertIn("generated_unit_0001.cpp:1", report)


if __name__ == "__main__":
    unittest.main()
