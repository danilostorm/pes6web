import unittest
from tools.patch_psp_umd_callback_dispatch import plan


class UmdCallbackDispatchTests(unittest.TestCase):
    def fixture(self):
        header = ('    std::set<std::int32_t> callbacks_;\n'
                  '    void sceUmdRegisterUMDCallBack(Ctx &ctx);\n')
        kernel = (
            'void Kernel::sceKernelCreateCallback(Ctx &ctx) {\n'
            '    const auto uid = new_uid();\n'
            '    callbacks_.insert(uid);\n'
            '    finish(ctx, static_cast<std::uint32_t>(uid));\n'
            '}\n'
            '    if (umd_callback_id_ == uid) umd_callback_id_ = 0;\n'
            'void Kernel::sceKernelCheckCallback(Ctx &ctx) { finish(ctx, 0u); }\n'
        )
        devices = (
            '    hle("sceUmdUser", 0xC6183D47u, "sceUmdActivate", &Kernel::return_zero);\n'
            'void Kernel::sceUmdCheckMedium(Ctx &ctx) { finish(ctx, 1u); }\n'
        )
        return header, kernel, devices

    def test_queue_is_delivered_to_guest(self):
        h, k, d, changed = plan(*self.fixture())
        self.assertTrue(changed)
        self.assertIn("callback_details_[uid]", k)
        self.assertIn("call_guest(ctx, cb.entry, {1u, reason, cb.common}", k)
        self.assertIn("0x32u", d)
        self.assertIn("sceUmdActivate(Ctx &ctx)", h)
        self.assertIn("callback_details_.erase(uid)", k)

    def test_idempotent(self):
        h, k, d, _ = plan(*self.fixture())
        h2, k2, d2, changed = plan(h, k, d)
        self.assertFalse(changed)
        self.assertEqual((h, k, d), (h2, k2, d2))

    def test_incompatible_upstream_is_rejected(self):
        h, k, d = self.fixture()
        with self.assertRaises(RuntimeError):
            plan(h.replace("callbacks_", "other_set_"), k, d)


if __name__ == "__main__":
    unittest.main()
