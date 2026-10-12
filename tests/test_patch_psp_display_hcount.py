import unittest
from tools.patch_psp_display_hcount import plan


class DisplayHcountTests(unittest.TestCase):
    def fixture(self):
        return (
            '    void sceDisplayGetFramePerSec(Ctx &ctx);\n',
            '    hle("sceDisplay", 0xDBA6C4C4u, "sceDisplayGetFramePerSec", &Kernel::sceDisplayGetFramePerSec);\n'
            'void Kernel::sceKernelLibcClock(Ctx &ctx) { finish(ctx, static_cast<std::uint32_t>(now_us())); }\n'
        )

    def test_nids_and_virtual_clock(self):
        h, d, changed = plan(*self.fixture())
        self.assertTrue(changed)
        self.assertIn("0x773DD3A3u", d)
        self.assertIn("0x210EAB3Au", d)
        self.assertIn("now_us() % kFrameUs", d)
        self.assertIn("display_.vcount", d)
        self.assertIn("sceDisplayGetCurrentHcount", h)

    def test_idempotency(self):
        h, d, _ = plan(*self.fixture())
        h2, d2, changed = plan(h, d)
        self.assertFalse(changed)
        self.assertEqual((h, d), (h2, d2))

    def test_abort_on_changed_upstream(self):
        h, d = self.fixture()
        with self.assertRaises(RuntimeError):
            plan(h.replace("sceDisplayGetFramePerSec", "foo"), d)


if __name__ == "__main__":
    unittest.main()
