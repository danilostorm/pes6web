import unittest
from tools.patch_psp_umdhle import plan


class BootHleTests(unittest.TestCase):
    def source(self):
        h = ('    void sceKernelCreateCallback(Ctx &ctx);\n'
             '    void sceUmdCheckMedium(Ctx &ctx);\n'
             '    std::map<std::int32_t, EventFlag> event_flags_;\n')
        k = ('void Kernel::sceKernelCreateCallback(Ctx &ctx) '
             '{ finish(ctx, static_cast<std::uint32_t>(new_uid())); }\n')
        d = ('    hle("sceUmdUser", 0x8EF08FCEu, "sceUmdWaitDriveStat", &Kernel::return_zero);\n'
             '    hle("Kernel_Library", 0xB55249D2u, "sceKernelIsCpuIntrEnable", &Kernel::return_one);\n'
             '    hle(util, 0x67AF3428u, "sceUtilityMsgDialogShutdownStart", &Kernel::sceUtilityMsgDialogShutdownStart);\n'
             '    hle(tm, 0xEDBA5844u, "sceKernelDeleteCallback", &Kernel::return_zero);\n'
             'void Kernel::sceUmdCheckMedium(Ctx &ctx) { finish(ctx, 1u); }\n')
        return h, k, d

    def test_registration(self):
        h, k, d, changed = plan(*self.source())
        self.assertTrue(changed)
        self.assertIn('callbacks_.insert(uid)', k)
        self.assertIn('sub_intrs_[key].enabled', d)
        for nid in ('0xAEE7404D', '0x4A9E5E29', '0xCA04A2B9', '0xFB8E22EC'):
            self.assertIn(nid, d)
        self.assertIn('0x32u', d)
        self.assertIn('callbacks_', h)

    def test_repeated_patch(self):
        h, k, d, _ = plan(*self.source())
        next_h, next_k, next_d, changed = plan(h, k, d)
        self.assertFalse(changed)
        self.assertEqual((next_h, next_k, next_d), (h, k, d))

    def test_fail_closed(self):
        h, k, d = self.source()
        with self.assertRaises(RuntimeError):
            plan(h.replace('sceUmdCheckMedium', 'unexpected'), k, d)


if __name__ == "__main__":
    unittest.main()
