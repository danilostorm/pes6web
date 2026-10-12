import unittest
from tools.patch_psp_ge_callback_trace import plan


class GeCallbackTraceTests(unittest.TestCase):
    def fixture(self):
        header = "    void sceGeGetCmd(Ctx &ctx);\n"
        kernel = (
            '    hle("sceGe_user", 0xA4FC06A4u, "sceGeSetCallback", &Kernel::return_zero);\n'
            "void Kernel::sceGeGetCmd(Ctx &ctx) { finish(ctx, 0u); }\n"
        )
        return header, kernel

    def test_bounded_trace_without_behavior_change(self):
        header, kernel, changed = plan(*self.fixture())
        self.assertTrue(changed)
        self.assertIn("void sceGeSetCallback(Ctx &ctx);", header)
        self.assertIn("printed++ < 4u", kernel)
        self.assertIn("std::memcpy(words, raw, sizeof(words));", kernel)
        self.assertIn("PES6_TRACE_GE_CALLBACK", kernel)
        self.assertIn("signal_fn=", kernel)
        self.assertIn("finish_fn=", kernel)
        self.assertIn("finish(ctx, 0u);", kernel)
        self.assertNotIn('"sceGeSetCallback", &Kernel::return_zero', kernel)

    def test_idempotent(self):
        header, kernel, _ = plan(*self.fixture())
        second_header, second_kernel, changed = plan(header, kernel)
        self.assertFalse(changed)
        self.assertEqual((header, kernel), (second_header, second_kernel))

    def test_partial_patch_refused(self):
        header, kernel = self.fixture()
        with self.assertRaises(RuntimeError):
            plan(header, kernel + "PES6_TRACE_GE_CALLBACK")
        with self.assertRaises(RuntimeError):
            plan(header.replace("sceGeGetCmd", "renamed"), kernel)


if __name__ == "__main__":
    unittest.main()
