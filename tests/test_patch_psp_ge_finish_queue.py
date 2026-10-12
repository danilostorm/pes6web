"""Static safety tests for the optional source-only GE FINISH bridge."""
import os
import unittest
from pathlib import Path
from tools.patch_psp_ge_finish_queue import plan, once, scoped


class GeFinishBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(os.environ.get(
            "PES6_UPSTREAM_CHECKOUT",
            str(Path(__file__).resolve().parents[1] / "work" / "psp-web-recomp")))
        cls.host = root / "PSPRecomp/profiles/web/host"
        cls.names = ("ge.hpp", "ge.cpp", "ge_worker.hpp",
                     "ge_worker.cpp", "kernel.hpp", "kernel.cpp")

    def test_rejects_ambiguous_source(self):
        with self.assertRaises(RuntimeError):
            once("repeated repeated", "repeated", "new", "wrong")
        with self.assertRaises(RuntimeError):
            scoped("A XX A YY B", "A", "B", "XX", "ZZ", "wrong")

    def test_real_source_plan_is_idempotent_and_opt_in(self):
        if not self.host.exists():
            self.skipTest("Pinned host source unavailable on this runner")
        before = {name: (self.host / name).read_text() for name in self.names}
        after, changed = plan(before)
        self.assertIsInstance(changed, bool)
        repeated, second = plan(after)
        self.assertFalse(second)
        self.assertEqual(after, repeated)
        self.assertIn('PES6_ENABLE_GE_FINISH_CALLBACKS', after['kernel.cpp'])
        self.assertIn('std::getenv("PES6_ENABLE_GE_FINISH_CALLBACKS") == nullptr', after['kernel.cpp'])
        self.assertIn('guest_calls_[uid] = GuestCall{-1, {}}', after['kernel.cpp'])
        self.assertIn('ge_list_callback_ids_.size() > 8192u', after['kernel.cpp'])
        self.assertIn('finish_events_.size() < 4096u', after['ge_worker.cpp'])
        self.assertIn('std::lock_guard<std::mutex>', after['ge_worker.cpp'])
        self.assertIn('capture_finish(id)', after['ge_worker.cpp'])
        self.assertIn('capture_finish(stalled_id_)', after['ge_worker.cpp'])
        self.assertIn('last_finish_ = GeFinish{true, data, pc_}', after['ge.cpp'])
        self.assertIn('Kernel::sceGeUnsetCallback(Ctx &ctx)', after['kernel.cpp'])
        self.assertEqual(after['kernel.cpp'].count('Kernel::poll_ge_finish_callbacks()'), 1)


if __name__ == "__main__":
    unittest.main()
