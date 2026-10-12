"""Open-source host HLE patch contract; no game files or ISO access."""
import unittest
from pathlib import Path

from tools.patch_psp_raw_sector_io import plan, once_in_function, RAW_HELPER


class RawSectorPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        root = Path(os.environ.get("PES6_UPSTREAM_CHECKOUT", str(
            Path(__file__).resolve().parents[1] / "work" / "psp-web-recomp")))
        cls.upstream = root / "PSPRecomp" / "profiles" / "web" / "host"
        # On Unraid the separately provisioned upstream checkout is mounted
        # outside the public source repo. Tests work without that checkout too.
        if not (cls.upstream / "io.cpp").exists():
            cls.upstream = None

    def test_scoped_function_edit(self):
        original = (
            "void Kernel::sceIoLseek(Ctx &ctx) { X; }\n"
            "void Kernel::sceIoLseek32(Ctx &ctx) { X; }\n"
            "void Kernel::sceIoGetstat(Ctx &ctx) { Y; }\n"
        )
        patched = once_in_function(original,
            "void Kernel::sceIoLseek(Ctx &ctx) {",
            "void Kernel::sceIoLseek32(Ctx &ctx) {",
            "X;", "Q;", "64-bit seek")
        self.assertIn("sceIoLseek(Ctx &ctx) { Q;", patched)
        self.assertIn("sceIoLseek32(Ctx &ctx) { X;", patched)

    def test_ambiguous_anchor_fails_closed(self):
        original = ("void Kernel::sceIoLseek(Ctx &ctx) { X; X; }\n"
                    "void Kernel::sceIoLseek32(Ctx &ctx) { }\n")
        with self.assertRaises(RuntimeError):
            once_in_function(original,
                "void Kernel::sceIoLseek(Ctx &ctx) {",
                "void Kernel::sceIoLseek32(Ctx &ctx) {",
                "X;", "Q;", "ambiguous")

    def test_parser_is_bounded_and_accepts_both_psp_disc_prefixes(self):
        self.assertIn('disc0:/sce_lbn0x', RAW_HELPER)
        self.assertIn('umd0:/sce_lbn0x', RAW_HELPER)
        self.assertIn("std::from_chars", RAW_HELPER)
        self.assertIn("sector > std::numeric_limits<std::uint64_t>::max() / 2048u", RAW_HELPER)
        self.assertIn("length > static_cast<std::uint64_t>(end) - base", RAW_HELPER)
        self.assertIn('std::getenv("PES6_DISC_ISO")', RAW_HELPER)
        self.assertIn("#if defined(__EMSCRIPTEN__)", RAW_HELPER)

    def test_pinned_open_source_host_patch_and_idempotence(self):
        if self.upstream is None:
            self.skipTest("Pinned upstream source not present (GitHub CI)")
        h = (self.upstream / "kernel.hpp").read_text()
        io = (self.upstream / "io.cpp").read_text()
        header, io_patched, changed = plan(h, io)
        self.assertTrue(changed)
        self.assertIn("raw_lbn{}", header)
        self.assertIn("raw_sector_read", io_patched)
        self.assertEqual(io_patched.count("PES6_RAW_LBN_IO"), 1)
        self.assertEqual(io_patched.count("if (it != files_.end() && it->second.raw_lbn)"), 2)
        header2, io2, changed2 = plan(header, io_patched)
        self.assertFalse(changed2)
        self.assertEqual((header, io_patched), (header2, io2))


if __name__ == "__main__":
    unittest.main()