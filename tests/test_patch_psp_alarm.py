import unittest
from tools.patch_psp_alarm import plan


class AlarmPatchTests(unittest.TestCase):
    def original(self):
        h = ('    void sceKernelGetSystemTimeLow(Ctx &ctx);\n'
             '    std::map<std::int32_t, GuestCall> guest_calls_;   // callback thread uid -> waiting caller\n')
        k = ('    hle(tm, 0xE81CAF8Fu, "sceKernelCreateCallback", &Kernel::sceKernelCreateCallback);\n'
             'void Kernel::sceKernelGetSystemTimeLow(Ctx &ctx) {\n'
             'void Kernel::poll_waits() {\n    const std::uint64_t now = now_us();\n'
             '    return earliest;\n}\n\nvoid Kernel::start_thread(')
        return h, k

    def test_alarm_registration_and_guest_handler(self):
        h, k, changed = plan(*self.original())
        self.assertTrue(changed)
        self.assertIn('0x6652B8CAu', k)
        self.assertIn('alarms_[uid] = alarm', k)
        self.assertIn('pspweb_alarm', k)
        self.assertIn('guest_calls_[tid]', k)
        self.assertIn('delay == 0u', k)
        self.assertIn('alarms_', h)

    def test_idempotent(self):
        h, k, _ = plan(*self.original())
        hh, kk, changed = plan(h, k)
        self.assertFalse(changed)
        self.assertEqual((hh, kk), (h, k))

    def test_rejects_mismatched_runtime(self):
        with self.assertRaises(RuntimeError):
            plan('unexpected header', 'unexpected kernel')


if __name__ == '__main__':
    unittest.main()
