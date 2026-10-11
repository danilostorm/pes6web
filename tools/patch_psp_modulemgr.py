#!/usr/bin/env python3
"""Apply an idempotent, source-only HLE fix to pinned PSP Web Recomp checkout.

The public PES6Web repository must not contain proprietary game code. This
script edits only open-source kernel host source files in the local work dir.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(source: str, needle: str, replacement: str, name: str) -> tuple[str, bool]:
    if replacement in source:
        return source, False
    if source.count(needle) != 1:
        raise RuntimeError(f"{name}: expected exactly one upstream anchor (found {source.count(needle)})")
    return source.replace(needle, replacement, 1), True


def plan_patch(cpp: str, hpp: str) -> tuple[str, str, bool]:
    changed = False
    new_hpp, did = replace_once(
        hpp,
        "    void sceKernelLoadModule(Ctx &ctx);\n",
        "    void sceKernelGetModuleIdByAddress(Ctx &ctx);\n"
        "    void sceKernelLoadModule(Ctx &ctx);\n",
        "kernel.hpp declaration",
    )
    changed |= did
    new_cpp, did = replace_once(
        cpp,
        '    const char *mm = "ModuleMgrForUser";\n',
        '    const char *mm = "ModuleMgrForUser";\n'
        '    hle(mm, 0xD8B73127u, "sceKernelGetModuleIdByAddress", &Kernel::sceKernelGetModuleIdByAddress);\n',
        "kernel.cpp NID registration",
    )
    changed |= did
    new_cpp, did = replace_once(
        new_cpp,
        "    blocks_[new_uid()] = MemoryBlock{std::move(name), address, align_up(size, 0x100u)};\n",
        "    // Keep a stable module UID associated with the guest executable range.\n"
        '    const bool is_module = name.rfind("module:", 0u) == 0u;\n'
        "    const std::int32_t uid = new_uid();\n"
        "    blocks_[uid] = MemoryBlock{std::move(name), address, align_up(size, 0x100u)};\n"
        "    if (is_module) modules_.insert(uid);\n",
        "kernel.cpp module registration",
    )
    changed |= did
    new_cpp, did = replace_once(
        new_cpp,
        "void Kernel::sceKernelLoadModule(Ctx &ctx) {\n",
        """void Kernel::sceKernelGetModuleIdByAddress(Ctx &ctx) {
    const std::uint32_t address = ctx.gpr[4];
    for (const std::int32_t uid : modules_) {
        const auto block_it = blocks_.find(uid);
        if (block_it == blocks_.end()) continue;
        const MemoryBlock &block = block_it->second;
        if (block.name.rfind("module:", 0u) != 0u) continue;
        // Subtraction after comparison avoids overflowing address + size.
        if (address >= block.address && address - block.address < block.size) {
            finish(ctx, static_cast<std::uint32_t>(uid));
            return;
        }
    }
    finish(ctx, 0x8002012Eu); // SCE_KERNEL_ERROR_UNKNOWN_MODULE
}

void Kernel::sceKernelLoadModule(Ctx &ctx) {
""",
        "kernel.cpp module lookup",
    )
    changed |= did
    return new_cpp, new_hpp, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path, help="PSP Web Recomp checkout containing profile/host")
    args = parser.parse_args()
    directory = args.upstream / "profile" / "host"
    cpp_path = directory / "kernel.cpp"
    hpp_path = directory / "kernel.hpp"
    cpp, hpp = cpp_path.read_text(), hpp_path.read_text()
    new_cpp, new_hpp, changed = plan_patch(cpp, hpp)
    if changed:
        # Plan both edits before writing either; missing anchors fail before mutation.
        if new_cpp != cpp:
            cpp_path.write_text(new_cpp)
        if new_hpp != hpp:
            hpp_path.write_text(new_hpp)
        print("PES6 HLE patch applied: sceKernelGetModuleIdByAddress (0xD8B73127)")
    else:
        print("PES6 HLE patch already applied; nothing changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
