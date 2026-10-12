import unittest
from tools.patch_psp_devctl import plan


class DevctlTests(unittest.TestCase):
    def source(self):
        return (
            "    void sceIoIoctl(Ctx &ctx);\n    std::int32_t umd_callback_id_{};\n",
            '    hle(io, 0x63632449u, "sceIoIoctl", &Kernel::sceIoIoctl);\n',
            "void Kernel::sceIoIoctl(Ctx &ctx) {\n",
        )

    def test_specific_psp_devctl_commands(self):
        h, k, io, changed = plan(*self.source())
        self.assertTrue(changed)
        self.assertIn("ms_callbacks_", h)
        self.assertIn("0x54F5FB11u", k)
        self.assertIn("0x02415821u", io)
        self.assertIn("0x02415822u", io)
        self.assertIn("callbacks_.contains(uid)", io)

    def test_idempotent(self):
        h, k, io, _ = plan(*self.source())
        out = plan(h, k, io)
        self.assertFalse(out[3])
        self.assertEqual(out[:3], (h, k, io))

    def test_unexpected_upstream_refused(self):
        h, k, io = self.source()
        with self.assertRaises(RuntimeError):
            plan(h.replace("sceIoIoctl", "other"), k, io)


if __name__ == "__main__":
    unittest.main()
