import unittest
from tools.patch_psp_modulemgr import plan_patch

class ModuleMgrPatchTests(unittest.TestCase):
    def sample(self):
        cpp = (
            '    const char *mm = "ModuleMgrForUser";\n'
            '    blocks_[new_uid()] = MemoryBlock{std::move(name), address, align_up(size, 0x100u)};\n'
            'void Kernel::sceKernelLoadModule(Ctx &ctx) {\n'
        )
        hpp = '    void sceKernelLoadModule(Ctx &ctx);\n'
        return cpp, hpp

    def test_implements_sce_kernel_get_module_id_by_address(self):
        cpp, hpp, changed = plan_patch(*self.sample())
        self.assertTrue(changed)
        self.assertIn('0xD8B73127u', cpp)
        self.assertIn('modules_.insert(uid)', cpp)
        self.assertIn('sceKernelGetModuleIdByAddress(Ctx &ctx)', cpp)
        self.assertIn('0x8002012Eu', cpp)
        self.assertIn('void sceKernelGetModuleIdByAddress', hpp)

    def test_idempotent_second_run(self):
        cpp, hpp, _ = plan_patch(*self.sample())
        cpp2, hpp2, changed = plan_patch(cpp, hpp)
        self.assertFalse(changed)
        self.assertEqual((cpp, hpp), (cpp2, hpp2))

    def test_unexpected_upstream_fails_instead_of_partial_patching(self):
        cpp, hpp = self.sample()
        with self.assertRaises(RuntimeError):
            plan_patch(cpp.replace('ModuleMgrForUser', 'OtherModule'), hpp)

if __name__ == '__main__':
    unittest.main()
