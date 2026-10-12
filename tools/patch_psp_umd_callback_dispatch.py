#!/usr/bin/env python3
"""Idempotent source-only UMD callback notification patch for pinned PSPWeb.

The fixed ISO reports READY on UMD activation.  The earlier HLE recorded the
callback ID but never dispatched its guest function; sceKernelCheckCallback
always returned 0.  This patch queues the activation event and delivers it
with the runtime's existing call_guest trampoline.
"""
from pathlib import Path
import argparse


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if new in source:
        return source
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: incompatible upstream or partial patch")
    return source.replace(old, new, 1)


def plan(header: str, kernel: str, devices: str) -> tuple[str, str, str, bool]:
    initial = (header, kernel, devices)
    header = replace_once(
        header,
        "    std::set<std::int32_t> callbacks_;\n",
        "    std::set<std::int32_t> callbacks_;\n"
        "    struct GuestCallback { std::uint32_t entry{}, common{}, pending{}; };\n"
        "    std::map<std::int32_t, GuestCallback> callback_details_;\n",
        "callback state",
    )
    header = replace_once(
        header,
        "    void sceUmdRegisterUMDCallBack(Ctx &ctx);\n",
        "    void sceUmdRegisterUMDCallBack(Ctx &ctx);\n"
        "    void sceUmdActivate(Ctx &ctx);\n",
        "activation declaration",
    )
    kernel = replace_once(
        kernel,
        """void Kernel::sceKernelCreateCallback(Ctx &ctx) {
    const auto uid = new_uid();
    callbacks_.insert(uid);
    finish(ctx, static_cast<std::uint32_t>(uid));
}""",
        """void Kernel::sceKernelCreateCallback(Ctx &ctx) {
    const auto uid = new_uid();
    callbacks_.insert(uid);
    callback_details_[uid] = GuestCallback{ctx.gpr[5], ctx.gpr[6], 0u};
    finish(ctx, static_cast<std::uint32_t>(uid));
}""",
        "store callback handler",
    )
    kernel = replace_once(
        kernel,
        "    if (umd_callback_id_ == uid) umd_callback_id_ = 0;\n",
        "    if (umd_callback_id_ == uid) umd_callback_id_ = 0;\n"
        "    callback_details_.erase(uid);\n",
        "delete callback",
    )
    kernel = replace_once(
        kernel,
        "void Kernel::sceKernelCheckCallback(Ctx &ctx) { finish(ctx, 0u); }",
        """void Kernel::sceKernelCheckCallback(Ctx &ctx) {
    for (auto &[uid, cb] : callback_details_) {
        (void)uid;
        if (cb.pending == 0u || cb.entry == 0u) continue;
        const auto reason = cb.pending;
        cb.pending = 0u;
        // PSP callback: notification count, event state, user common pointer.
        call_guest(ctx, cb.entry, {1u, reason, cb.common},
                   [](std::uint32_t) { return 1u; });
        return;
    }
    finish(ctx, 0u);
}""",
        "callback dispatcher",
    )
    devices = replace_once(
        devices,
        '    hle("sceUmdUser", 0xC6183D47u, "sceUmdActivate", &Kernel::return_zero);\n',
        '    hle("sceUmdUser", 0xC6183D47u, "sceUmdActivate", &Kernel::sceUmdActivate);\n',
        "activation registration",
    )
    devices = replace_once(
        devices,
        "void Kernel::sceUmdCheckMedium(Ctx &ctx) { finish(ctx, 1u); }\n",
        """void Kernel::sceUmdCheckMedium(Ctx &ctx) { finish(ctx, 1u); }

void Kernel::sceUmdActivate(Ctx &ctx) {
    const auto mode = ctx.gpr[4];
    const auto name = read_string(ctx.gpr[5], 16u);
    if (mode != 1u || name.rfind("disc0:", 0u) != 0u) {
        finish(ctx, 0x80010016u);
        return;
    }
    if (umd_callback_id_ != 0) {
        const auto it = callback_details_.find(umd_callback_id_);
        if (it != callback_details_.end()) {
            // PSP_UMD_PRESENT | PSP_UMD_READY | PSP_UMD_READABLE.
            it->second.pending |= 0x32u;
        }
    }
    finish(ctx, 0u);
}
""",
        "activation handler",
    )
    return header, kernel, devices, initial != (header, kernel, devices)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    root = args.checkout / "PSPRecomp/profiles/web/host"
    files = [root / x for x in ("kernel.hpp", "kernel.cpp", "devices.cpp")]
    before = [f.read_text() for f in files]
    out = plan(*before)
    if out[3]:
        for file, old, new in zip(files, before, out[:3]):
            if old != new:
                file.write_text(new)
    print("UMD PSP guest callback dispatch:", "applied" if out[3] else "already applied")


if __name__ == "__main__":
    main()
