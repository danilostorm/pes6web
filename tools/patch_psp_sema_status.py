#!/usr/bin/env python3
"""Implement PSP sceKernelReferSemaStatus with its 56-byte guest struct.

A previous generic HLE fallback returned success without writing the
semaphore status, leaving a PSP title with uninitialized results.
"""
from pathlib import Path
import argparse


def once(source: str, before: str, after: str) -> str:
    if after in source:
        return source
    if source.count(before) != 1:
        raise RuntimeError("Unexpected upstream semaphore source; refusing patch")
    return source.replace(before, after, 1)


def plan(header: str, kernel: str) -> tuple[str, str, bool]:
    old = (header, kernel)
    header = once(header, """struct Semaphore {
    std::string name;
    std::int32_t count{};
    std::int32_t max{};
};""", """struct Semaphore {
    std::string name;
    std::int32_t count{};
    std::int32_t max{};
    std::int32_t initial{};
    std::uint32_t attr{};
};""")
    header = once(
        header,
        "    void sceKernelCreateSema(Ctx &ctx);\n",
        "    void sceKernelCreateSema(Ctx &ctx);\n"
        "    void sceKernelReferSemaStatus(Ctx &ctx);\n",
    )
    kernel = once(
        kernel,
        '    hle(tm, 0xD6DA4BA1u, "sceKernelCreateSema", &Kernel::sceKernelCreateSema);\n',
        '    hle(tm, 0xD6DA4BA1u, "sceKernelCreateSema", &Kernel::sceKernelCreateSema);\n'
        '    hle(tm, 0xBC6FEBC5u, "sceKernelReferSemaStatus", &Kernel::sceKernelReferSemaStatus);\n',
    )
    kernel = once(
        kernel,
        """    semaphores_[uid] = Semaphore{read_string(ctx.gpr[4], 32), static_cast<std::int32_t>(ctx.gpr[6]),
                                 static_cast<std::int32_t>(ctx.gpr[7])};""",
        """    semaphores_[uid] = Semaphore{read_string(ctx.gpr[4], 32), static_cast<std::int32_t>(ctx.gpr[6]),
                                 static_cast<std::int32_t>(ctx.gpr[7]),
                                 static_cast<std::int32_t>(ctx.gpr[6]), ctx.gpr[5]};""",
    )
    kernel = once(
        kernel,
        "void Kernel::sceKernelDeleteSema(Ctx &ctx) {\n",
        """void Kernel::sceKernelReferSemaStatus(Ctx &ctx) {
    const auto uid = static_cast<std::int32_t>(ctx.gpr[4]);
    const auto it = semaphores_.find(uid);
    if (it == semaphores_.end()) { finish(ctx, kErrorUnknownSema); return; }
    const auto address = ctx.gpr[5];
    if (address == 0u) { finish(ctx, 0x800200D3u); return; }
    const auto size = rt_.memory().load32(address);
    constexpr std::uint32_t kInfoSize = 56u;
    if (size < kInfoSize) { finish(ctx, 0x800200D3u); return; }

    const auto &sema = it->second;
    rt_.memory().store32(address, kInfoSize);
    for (std::uint32_t i = 0; i < 32u; ++i)
        rt_.memory().store8(address + 4u + i,
                            i < sema.name.size() ? static_cast<std::uint8_t>(sema.name[i]) : 0u);
    rt_.memory().store32(address + 36u, sema.attr);
    rt_.memory().store32(address + 40u, static_cast<std::uint32_t>(sema.initial));
    rt_.memory().store32(address + 44u, static_cast<std::uint32_t>(sema.count));
    rt_.memory().store32(address + 48u, static_cast<std::uint32_t>(sema.max));
    std::uint32_t waiters = 0u;
    for (const auto &[tid, thread] : threads_) {
        (void)tid;
        if (thread.state == ThreadState::Waiting &&
            thread.wait == WaitType::Sema && thread.wait_uid == uid) ++waiters;
    }
    rt_.memory().store32(address + 52u, waiters);
    finish(ctx, 0u);
}

void Kernel::sceKernelDeleteSema(Ctx &ctx) {
""",
    )
    return header, kernel, old != (header, kernel)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    folder = args.checkout / "PSPRecomp/profiles/web/host"
    h, k = folder / "kernel.hpp", folder / "kernel.cpp"
    newh, newk, changed = plan(h.read_text(), k.read_text())
    if changed:
        h.write_text(newh)
        k.write_text(newk)
    print("PSP sema status HLE:", "applied" if changed else "already applied")


if __name__ == "__main__":
    main()
