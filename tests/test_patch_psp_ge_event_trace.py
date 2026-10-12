import unittest
from tools.patch_psp_ge_event_trace import plan


class GeEventTraceTests(unittest.TestCase):
    def fixture(self):
        return (
            "    ++stats_.lists;\n    pc_ = start & 0x0FFFFFFFu;\n"
            "        if ((op >> 24u) == kEnd) return true;\n"
            "    const std::uint32_t data = op & 0x00FFFFFFu;\n    switch (cmd) {\n"
        )

    def test_finite_opt_in_trace(self):
        patched, changed = plan(self.fixture())
        self.assertTrue(changed)
        self.assertIn("PES6_TRACE_GE_EVENTS", patched)
        self.assertIn("cmd == 0x0Eu || cmd == kFinish", patched)
        self.assertIn("printed_lists++ < 12u", patched)
        self.assertIn("ends++ < 24u", patched)
        self.assertIn("events++ < 36u", patched)
        self.assertIn("[ge-event]", patched)
        self.assertIn("[ge-list]", patched)

    def test_idempotent(self):
        patched, _ = plan(self.fixture())
        repeated, changed = plan(patched)
        self.assertFalse(changed)
        self.assertEqual(repeated, patched)

    def test_unknown_source_refused(self):
        with self.assertRaises(RuntimeError):
            plan("unexpected source")


if __name__ == "__main__":
    unittest.main()
