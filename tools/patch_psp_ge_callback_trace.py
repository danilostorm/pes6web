#!/usr/bin/env python3
"""Bounded opt-in GE callback registration trace for pinned PSPWeb host.

Preserves existing sceGeSetCallback behavior while logging only the four
function/argument pointers in the guest SceGeCallbackData. No commercial game
bytes or assets are logged. Use PES6_TRACE_GE_CALLBACK=1 for private tests.
"""
import argparse
from pathlib import Path


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: pinned upstream changed or patch is partial")
    return text.replace(old, new, 1)


def plan(header: str, kernel: str) -> tuple[str, str, bool]:
    marker = "PES6_TRACE_GE_CALLBACK"
    if marker in kernel:
        if (kernel.count(marker) != 1 or
                "Kernel::sceGeSetCallback(Ctx &ctx)" not in kernel or
                '"sceGeSetCallback", &Kernel::sceGeSetCallback' not in kernel or
                "void sceGeSetCallback(Ctx &ctx);" not in header):
            raise RuntimeError("Partially installed GE callback trace")
        return header, kernel, False

    new_header = replace_exact(
        header,
        "    void sceGeGetCmd(Ctx &ctx);\n",
        "    void sceGeSetCallback(Ctx &ctx);\n    void sceGeGetCmd(Ctx &ctx);\n",
        "callback declaration",
    )
    new_kernel = replace_exact(
        kernel,
        '    hle("sceGe_user", 0xA4FC06A4u, "sceGeSetCallback", &Kernel::return_zero);\n',
        '    hle("sceGe_user", 0xA4FC06A4u, "sceGeSetCallback", &Kernel::sceGeSetCallback);\n',
        "callback HLE registration",
    )
    new_kernel = replace_exact(
        new_kernel,
        "void Kernel::sceGeGetCmd(Ctx &ctx) { finish(ctx, 0u); }\n",
        """void Kernel::sceGeSetCallback(Ctx &ctx) {
    // Opt-in diagnostics: do not change the pre-existing return value or
    // attempt guest callback dispatch from the GE worker thread.
    static std::uint32_t printed = 0u;
    if (std::getenv("PES6_TRACE_GE_CALLBACK") != nullptr && printed++ < 4u) {
        const auto address = ctx.gpr[4];
        const auto *raw = rt_.memory().raw_pointer(address, 16u);
        if (raw != nullptr) {
            std::uint32_t words[4]{};
            std::memcpy(words, raw, sizeof(words));
            std::cerr << "[ge-callback] data=" << hex(address)
                      << " signal_fn=" << hex(words[0])
                      << " signal_arg=" << hex(words[1])
                      << " finish_fn=" << hex(words[2])
                      << " finish_arg=" << hex(words[3]) << "\\n";
        } else {
            std::cerr << "[ge-callback] data=" << hex(address)
                      << " invalid_guest_pointer\\n";
        }
    }
    finish(ctx, 0u);
}

void Kernel::sceGeGetCmd(Ctx &ctx) { finish(ctx, 0u); }
""",
        "callback diagnostic implementation",
    )
    return new_header, new_kernel, (new_header, new_kernel) != (header, kernel)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    base = args.checkout / "PSPRecomp/profiles/web/host"
    header_path = base / "kernel.hpp"
    kernel_path = base / "kernel.cpp"
    header, kernel, changed = plan(header_path.read_text(), kernel_path.read_text())
    if changed:
        header_path.write_text(header)
        kernel_path.write_text(kernel)
    print("PSP GE callback trace:", "installed" if changed else "already installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
