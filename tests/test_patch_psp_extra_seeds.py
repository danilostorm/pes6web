import unittest
from tools.patch_psp_extra_seeds import plan, INCLUDES_ANCHOR, SEED_ANCHOR

class ExtraSeedsTests(unittest.TestCase):
    def sample(self):
        return INCLUDES_ANCHOR + SEED_ANCHOR

    def test_add_extra_seeds(self):
        changed, did = plan(self.sample())
        self.assertTrue(did)
        self.assertIn('PSPRECOMP_EXTRA_SEEDS', changed)
        self.assertIn('program.seeds.try_emplace', changed)
        self.assertIn('is_executable_address', changed)

    def test_repeat_is_idempotent(self):
        first, _ = plan(self.sample())
        again, did = plan(first)
        self.assertFalse(did)
        self.assertEqual(first, again)

    def test_refuse_unknown_upstream(self):
        with self.assertRaises(RuntimeError):
            plan('unexpected new code')

if __name__ == '__main__':
    unittest.main()
