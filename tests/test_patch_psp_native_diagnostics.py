import unittest
from tools.patch_psp_native_diagnostics import plan, ANCHOR


class NativeDiagnosticsTests(unittest.TestCase):
    def test_early_exit_counters_and_idempotency(self):
        patched, changed = plan(ANCHOR)
        self.assertTrue(changed)
        self.assertIn('ge-exit lists=', patched)
        self.assertIn('gl-exit draw_calls=', patched)
        again, changed = plan(patched)
        self.assertFalse(changed)
        self.assertEqual(again, patched)

    def test_unknown_upstream_fails(self):
        with self.assertRaises(RuntimeError):
            plan("No native host runner exists")


if __name__ == "__main__":
    unittest.main()
