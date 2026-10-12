#!/usr/bin/env python3
"""Implement PSP display Hcount timing instead of falling back to zero.

Source-only patch. Timing is approximated from existing virtual guest clock
(16,683 us per frame, 286 Hcount increments per frame).
"""
from pathlib import Path
import argparse


def replace_once(source: str, original: str, replacement: str) -> str:
    if replacement in source:
        return source
    if source.count(original) != 1:
        raise RuntimeError("Unexpected PSPRecomp display source layout")
    return source.replace(original, replacement, 1)


def plan(header: str, devices: str) -> tuple[str, str, bool]:
    old = (header, devices)
    header = replace_once(
        header,
        "    void sceDisplayGetFramePerSec(Ctx &ctx);\n",
        "    void sceDisplayGetFramePerSec(Ctx &ctx);\n"
        "    void sceDisplayGetCurrentHcount(Ctx &ctx);\n"
        "    void sceDisplayGetAccumulatedHcount(Ctx &ctx);\n",
    )
    devices = replace_once(
        devices,
        '    hle("sceDisplay", 0xDBA6C4C4u, "sceDisplayGetFramePerSec", &Kernel::sceDisplayGetFramePerSec);\n',
        '    hle("sceDisplay", 0xDBA6C4C4u, "sceDisplayGetFramePerSec", &Kernel::sceDisplayGetFramePerSec);\n'
        '    hle("sceDisplay", 0x773DD3A3u, "sceDisplayGetCurrentHcount", &Kernel::sceDisplayGetCurrentHcount);\n'
        '    hle("sceDisplay", 0x210EAB3Au, "sceDisplayGetAccumulatedHcount", &Kernel::sceDisplayGetAccumulatedHcount);\n',
    )
    devices = replace_once(
        devices,
        "void Kernel::sceKernelLibcClock(Ctx &ctx) { finish(ctx, static_cast<std::uint32_t>(now_us())); }\n",
        """// Virtual scanline timing: 286 horizontal counts per 59.94 Hz frame.
void Kernel::sceDisplayGetCurrentHcount(Ctx &ctx) {
    constexpr std::uint64_t kFrameUs = 16683u;
    const std::uint32_t scanline = 1u + static_cast<std::uint32_t>((now_us() % kFrameUs) * 286u / kFrameUs);
    finish(ctx, scanline);
}
void Kernel::sceDisplayGetAccumulatedHcount(Ctx &ctx) {
    constexpr std::uint64_t kFrameUs = 16683u;
    const auto scanline = 1u + (now_us() % kFrameUs) * 286u / kFrameUs;
    const auto value = (static_cast<std::uint64_t>(display_.vcount) * 286u + scanline) & 0x7FFFFFFFu;
    finish(ctx, static_cast<std::uint32_t>(value));
}
void Kernel::sceKernelLibcClock(Ctx &ctx) { finish(ctx, static_cast<std::uint32_t>(now_us())); }
""",
    )
    return header, devices, old != (header, devices)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("checkout", type=Path)
    args = p.parse_args()
    host = args.checkout / "PSPRecomp/profiles/web/host"
    h, d = host / "kernel.hpp", host / "devices.cpp"
    newh, newd, changed = plan(h.read_text(), d.read_text())
    if changed:
        h.write_text(newh)
        d.write_text(newd)
    print("PSP display scanline Hcount HLE:", "applied" if changed else "already applied")


if __name__ == "__main__":
    main()
