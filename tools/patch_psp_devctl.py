#!/usr/bin/env python3
"""Source-only PSP Memory Stick callback devctl support (fatms0:)."""
import argparse
from pathlib import Path


def once(s, before, after):
    if after in s:
        return s
    if s.count(before) != 1:
        raise RuntimeError("Unknown upstream IoFileMgr source revision")
    return s.replace(before, after, 1)


def plan(h, k, io):
    previous = (h, k, io)
    h = once(h, "    void sceIoIoctl(Ctx &ctx);\n",
        "    void sceIoIoctl(Ctx &ctx);\n"
        "    void sceIoDevctl(Ctx &ctx);\n")
    h = once(h, "    std::int32_t umd_callback_id_{};\n",
        "    std::int32_t umd_callback_id_{};\n"
        "    std::set<std::int32_t> ms_callbacks_;\n")
    k = once(k, '    hle(io, 0x63632449u, "sceIoIoctl", &Kernel::sceIoIoctl);\n',
        '    hle(io, 0x63632449u, "sceIoIoctl", &Kernel::sceIoIoctl);\n'
        '    hle(io, 0x54F5FB11u, "sceIoDevctl", &Kernel::sceIoDevctl);\n')
    io = once(io, "void Kernel::sceIoIoctl(Ctx &ctx) {\n",
        """void Kernel::sceIoDevctl(Ctx &ctx) {
    // PSP fatms0: control requests are not ordinary file descriptors.
    // The in-memory Memory Stick is always inserted in this web profile.
    const std::string device = read_string(ctx.gpr[4], 32u);
    const auto command = ctx.gpr[5];
    if (device != "fatms0:") { finish(ctx, 0x80010016u); return; }
    if (command == 0x0240D81Eu) { finish(ctx, 0u); return; } // invalidate FAT cache
    if (command == 0x02415821u || command == 0x02415822u) {
        if (ctx.gpr[6] == 0u || ctx.gpr[7] < 4u) {
            finish(ctx, 0x80010016u); return;
        }
        const auto uid = static_cast<std::int32_t>(rt_.memory().load32(ctx.gpr[6]));
        if (command == 0x02415821u) { // insert/eject callback registration
            if (!callbacks_.contains(uid) || ms_callbacks_.size() >= 32u) {
                finish(ctx, 0x80010016u); return;
            }
            ms_callbacks_.insert(uid);
        } else if (ms_callbacks_.erase(uid) == 0u) {
            finish(ctx, 0x80010016u); return;
        }
        // TODO: deliver inserted-state notification via guest callbacks.
        finish(ctx, 0u);
        return;
    }
    finish(ctx, 0x80010016u); // no generic success for unknown device commands
}

void Kernel::sceIoIoctl(Ctx &ctx) {
""")
    return h, k, io, (h, k, io) != previous


def main():
    p = argparse.ArgumentParser()
    p.add_argument("checkout", type=Path)
    args = p.parse_args()
    folder = args.checkout / "PSPRecomp/profiles/web/host"
    paths = [folder / "kernel.hpp", folder / "kernel.cpp", folder / "io.cpp"]
    old = [path.read_text() for path in paths]
    new = plan(*old)
    if new[3]:
        for path, before, after in zip(paths, old, new[:3]):
            if before != after:
                path.write_text(after)
    print("Memory Stick callback sceIoDevctl HLE:", "applied" if new[3] else "already applied")


if __name__ == "__main__":
    main()
