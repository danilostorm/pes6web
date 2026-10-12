"""Opt-in latency experiment: source-only tests and fail-closed contracts."""
import os
import unittest
from pathlib import Path
from tools.patch_psp_raw_async_delay import plan


class RawAsyncDelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ.get(
            "PES6_UPSTREAM_CHECKOUT",
            str(Path(__file__).resolve().parents[1] / "work" / "psp-web-recomp")))
        cls.host = root / "PSPRecomp/profiles/web/host"

    def test_patch_requires_raw_sector_support(self):
        with self.assertRaises(RuntimeError):
            plan("bad header", "bad io")

    def test_deferred_completion_remains_opt_in(self):
        if not (self.host / "io.cpp").exists():
            self.skipTest("Pinned upstream host source not present")
        header = (self.host / "kernel.hpp").read_text()
        io = (self.host / "io.cpp").read_text()
        new_h, new_io, changed = plan(header, io)
        self.assertIsInstance(changed, bool)
        h2, io2, changed2 = plan(new_h, new_io)
        self.assertFalse(changed2)
        self.assertEqual((new_h, new_io), (h2, io2))
        self.assertIn('std::getenv("PES6_RAW_ASYNC_DEFER")', new_io)
        self.assertIn('open.raw_async_due_frame <= display_.vcount', new_io)
        self.assertIn('open.async_pending = false;', new_io)
        self.assertIn('finish_async(fd);', new_io)
        self.assertIn('if (it->second.async_pending) {', new_io)
        self.assertIn('raw_sector_read(it->second, ctx.gpr[5], ctx.gpr[6])', new_io)
        self.assertIn('raw_async_due_frame{}', new_h)
        self.assertIn('std::vector<std::int32_t> ready;', new_io)
        self.assertLessEqual(new_io.count('PES6_RAW_ASYNC_DEFER'), 3)


if __name__ == "__main__":
    unittest.main()
