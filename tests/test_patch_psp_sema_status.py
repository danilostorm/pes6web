import unittest
from tools.patch_psp_sema_status import plan


class SemaStatusTests(unittest.TestCase):
    def sources(self):
        h = ('struct Semaphore {\n'
             '    std::string name;\n'
             '    std::int32_t count{};\n'
             '    std::int32_t max{};\n'
             '};\n'
             '    void sceKernelCreateSema(Ctx &ctx);\n')
        k = ('    hle(tm, 0xD6DA4BA1u, "sceKernelCreateSema", &Kernel::sceKernelCreateSema);\n'
             '    semaphores_[uid] = Semaphore{read_string(ctx.gpr[4], 32), static_cast<std::int32_t>(ctx.gpr[6]),\n'
             '                                 static_cast<std::int32_t>(ctx.gpr[7])};\n'
             'void Kernel::sceKernelDeleteSema(Ctx &ctx) {\n')
        return h, k

    def test_status_layout_and_registration(self):
        h, k, changed = plan(*self.sources())
        self.assertTrue(changed)
        self.assertIn("0xBC6FEBC5u", k)
        self.assertIn("kInfoSize = 56u", k)
        self.assertIn("address + 36u", k)
        self.assertIn("address + 52u", k)
        self.assertIn("ThreadState::Waiting", k)
        self.assertIn("initial{}", h)

    def test_repeat_safe(self):
        h, k, _ = plan(*self.sources())
        h2, k2, changed = plan(h, k)
        self.assertEqual((h, k), (h2, k2))
        self.assertFalse(changed)

    def test_incompatible_upstream(self):
        h, k = self.sources()
        with self.assertRaises(RuntimeError):
            plan(h.replace("struct Semaphore", "struct Changed"), k)


if __name__ == "__main__":
    unittest.main()
