#!/usr/bin/env python3
"""Minimal source-only PSP boot HLE additions. No retail game code involved.

Track created callback UIDs, fixed UMD readiness and sub-interrupt registrations.
Interrupt delivery and full firmware-module loading remain separate TODOs.
"""
from pathlib import Path
import argparse


def swap(source, before, after):
    if after in source:
        return source
    if source.count(before) != 1:
        raise RuntimeError("Changed upstream source anchor; refusing unsafe patch")
    return source.replace(before, after, 1)


def plan(h, k, d):
    base = (h, k, d)
    h = swap(h, "    void sceKernelCreateCallback(Ctx &ctx);\n",
             "    void sceKernelCreateCallback(Ctx &ctx);\n"
             "    void sceKernelDeleteCallback(Ctx &ctx);\n")
    h = swap(h, "    void sceUmdCheckMedium(Ctx &ctx);\n",
             "    void sceUmdCheckMedium(Ctx &ctx);\n"
             "    void sceUmdRegisterUMDCallBack(Ctx &ctx);\n"
             "    void sceUmdWaitDriveStatCB(Ctx &ctx);\n"
             "    void sceKernelRegisterSubIntrHandler(Ctx &ctx);\n"
             "    void sceKernelEnableSubIntr(Ctx &ctx);\n")
    h = swap(h, "    std::map<std::int32_t, EventFlag> event_flags_;\n",
             "    std::map<std::int32_t, EventFlag> event_flags_;\n"
             "    std::set<std::int32_t> callbacks_;\n"
             "    std::int32_t umd_callback_id_{};\n"
             "    struct SubIntr { std::uint32_t handler{}, arg{}; bool enabled{}; };\n"
             "    std::map<std::uint64_t, SubIntr> sub_intrs_;\n")

    k = swap(k, "void Kernel::sceKernelCreateCallback(Ctx &ctx) { finish(ctx, static_cast<std::uint32_t>(new_uid())); }\n",
             """void Kernel::sceKernelCreateCallback(Ctx &ctx) {
    const auto uid = new_uid();
    callbacks_.insert(uid);
    finish(ctx, static_cast<std::uint32_t>(uid));
}
void Kernel::sceKernelDeleteCallback(Ctx &ctx) {
    const auto uid = static_cast<std::int32_t>(ctx.gpr[4]);
    if (callbacks_.erase(uid) == 0u) { finish(ctx, kErrorUnknownUid); return; }
    if (umd_callback_id_ == uid) umd_callback_id_ = 0;
    finish(ctx, 0u);
}
""")
    d = swap(d,
             '    hle("sceUmdUser", 0x8EF08FCEu, "sceUmdWaitDriveStat", &Kernel::return_zero);\n',
             '    hle("sceUmdUser", 0x8EF08FCEu, "sceUmdWaitDriveStat", &Kernel::return_zero);\n'
             '    hle("sceUmdUser", 0xAEE7404Du, "sceUmdRegisterUMDCallBack", &Kernel::sceUmdRegisterUMDCallBack);\n'
             '    hle("sceUmdUser", 0x4A9E5E29u, "sceUmdWaitDriveStatCB", &Kernel::sceUmdWaitDriveStatCB);\n')
    d = swap(d,
             '    hle("Kernel_Library", 0xB55249D2u, "sceKernelIsCpuIntrEnable", &Kernel::return_one);\n',
             '    hle("Kernel_Library", 0xB55249D2u, "sceKernelIsCpuIntrEnable", &Kernel::return_one);\n'
             '    hle("InterruptManager", 0xCA04A2B9u, "sceKernelRegisterSubIntrHandler", &Kernel::sceKernelRegisterSubIntrHandler);\n'
             '    hle("InterruptManager", 0xFB8E22ECu, "sceKernelEnableSubIntr", &Kernel::sceKernelEnableSubIntr);\n')
    d = swap(d,
             '    hle(util, 0x67AF3428u, "sceUtilityMsgDialogShutdownStart", &Kernel::sceUtilityMsgDialogShutdownStart);\n',
             '    hle(util, 0x67AF3428u, "sceUtilityMsgDialogShutdownStart", &Kernel::sceUtilityMsgDialogShutdownStart);\n'
             '    // Firmware support is virtualized in the host; actual PRX loading is not performed.\n'
             '    hle(util, 0x1579A159u, "sceUtilityLoadNetModule", &Kernel::return_zero);\n'
             '    hle(util, 0x0D5BC6D2u, "sceUtilityLoadUsbModule", &Kernel::return_zero);\n'
             '    hle(util, 0xC629AF26u, "sceUtilityLoadAvModule", &Kernel::return_zero);\n')
    d = swap(d,
             '    hle(tm, 0xEDBA5844u, "sceKernelDeleteCallback", &Kernel::return_zero);\n',
             '    hle(tm, 0xEDBA5844u, "sceKernelDeleteCallback", &Kernel::sceKernelDeleteCallback);\n')
    d = swap(d, "void Kernel::sceUmdCheckMedium(Ctx &ctx) { finish(ctx, 1u); }\n",
             """void Kernel::sceUmdCheckMedium(Ctx &ctx) { finish(ctx, 1u); }

void Kernel::sceUmdRegisterUMDCallBack(Ctx &ctx) {
    const auto uid = static_cast<std::int32_t>(ctx.gpr[4]);
    if (!callbacks_.contains(uid)) { finish(ctx, kErrorUnknownUid); return; }
    umd_callback_id_ = uid;
    finish(ctx, 0u);
}
void Kernel::sceUmdWaitDriveStatCB(Ctx &ctx) {
    // The fixed ISO remains inserted, initialized and ready (0x02 | 0x10 | 0x20).
    if ((ctx.gpr[4] & 0x32u) == 0u) {
        finish(ctx, 0x800201A8u); // wait timed out for unavailable media state
        return;
    }
    finish(ctx, 0u);
}
void Kernel::sceKernelRegisterSubIntrHandler(Ctx &ctx) {
    const auto intr = ctx.gpr[4], sub = ctx.gpr[5];
    if (intr >= 67u || sub >= 32u) { finish(ctx, 0x80020065u); return; }
    const auto key = (static_cast<std::uint64_t>(intr) << 32u) | sub;
    auto &entry = sub_intrs_[key];
    if (entry.handler != 0u && ctx.gpr[6] != 0u) {
        finish(ctx, 0x80020067u);
        return;
    }
    entry.handler = ctx.gpr[6];
    entry.arg = ctx.gpr[7];
    // TODO: GE/vblank guest handler dispatch (currently only registration).
    finish(ctx, 0u);
}
void Kernel::sceKernelEnableSubIntr(Ctx &ctx) {
    const auto intr = ctx.gpr[4], sub = ctx.gpr[5];
    if (intr >= 67u || sub >= 32u) { finish(ctx, 0x80020065u); return; }
    const auto key = (static_cast<std::uint64_t>(intr) << 32u) | sub;
    sub_intrs_[key].enabled = true;
    finish(ctx, 0u);
}
""")
    return h, k, d, (h, k, d) != base


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    opts = parser.parse_args()
    base = opts.checkout / "PSPRecomp/profiles/web/host"
    files = [base / x for x in ("kernel.hpp", "kernel.cpp", "devices.cpp")]
    original = [p.read_text() for p in files]
    out = plan(*original)
    if out[3]:
        for p, before, after in zip(files, original, out[:3]):
            if before != after:
                p.write_text(after)
    print("UMD, callback and subinterrupt boot HLE:", "applied" if out[3] else "already applied")


if __name__ == "__main__":
    main()
