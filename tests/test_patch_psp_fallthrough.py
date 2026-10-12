import unittest
from tools.patch_psp_fallthrough import plan, ANCHOR, INSERT

class FallbackCfgTests(unittest.TestCase):
    def sample(self):
        return "#include <cstdlib>\n#include <sstream>\n" + ANCHOR

    def test_generates_bounded_executable_jump_scan(self):
        patched, changed = plan(self.sample())
        self.assertTrue(changed)
        self.assertIn('is_executable_address(program.executable_ranges, pc)', patched)
        self.assertIn('decoded.kind == OpcodeKind::Jr', patched)
        self.assertIn('PSPRECOMP_FALLTHROUGH_RANGES', patched)
        self.assertIn('hi - lo > 0x100000ull', patched)

    def test_idempotent(self):
        patched, _ = plan(self.sample())
        second, changed = plan(patched)
        self.assertFalse(changed)
        self.assertEqual(patched, second)

    def test_refuses_upstream_undetected(self):
        with self.assertRaises(RuntimeError):
            plan("other code" + ANCHOR)

if __name__ == "__main__":
    unittest.main()
