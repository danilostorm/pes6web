import unittest
from tools.patch_psp_private_diagnostics import plan_io, plan_ge


class PrivateTraceTests(unittest.TestCase):
    def io_fixture(self):
        return (
            '#include <cstring>\n'
            'constexpr std::uint64_t kMaxWholeFileRead = 256u << 20u;\n'
            '    files_[fd] = OpenFile{file, nullptr, 0u, psp_path};\n'
            '    finish(ctx, static_cast<std::uint32_t>(fd));\n'
            '    finish(ctx, static_cast<std::uint32_t>(std::fread(dst, 1u, ctx.gpr[6], it->second.file)));\n'
            '    const bool ok = open.web != nullptr || open.file != nullptr;\n'
            '    it->second.async_pending = false;\n'
            '    finish(ctx, 0u);\n'
            '}\n\nvoid Kernel::sceIoLseekAsync'
            '    const auto command = ctx.gpr[5];\n'
            '    if (device != "fatms0:")'
            '    if (command == 0x04100002u) { // where the PGD container starts inside the file'
        )

    def test_io_opt_in_and_reapply(self):
        s, did = plan_io(self.io_fixture())
        self.assertTrue(did)
        self.assertIn('PES6_TRACE_IO', s)
        self.assertIn('read-async', s)
        second, did = plan_io(s)
        self.assertFalse(did)
        self.assertEqual(s, second)

    def test_ge_first_18_entries_and_reapply(self):
        s, did = plan_ge('void Ge::draw_primitive(std::uint32_t type, std::uint32_t count) {\n    ++stats_.prims;\n')
        self.assertTrue(did)
        self.assertIn('PES6_TRACE_GE', s)
        self.assertIn('clear=', s)
        again, changed = plan_ge(s)
        self.assertFalse(changed)
        self.assertEqual(s, again)

    def test_unknown_upstream_aborts(self):
        with self.assertRaises(RuntimeError):
            plan_io('not the original source')
        with self.assertRaises(RuntimeError):
            plan_ge('not the original source')


if __name__ == "__main__":
    unittest.main()
