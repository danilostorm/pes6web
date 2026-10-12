#!/usr/bin/env python3
"""Optional private PSP native diagnostics: I/O path/byte counts and GE clear state.

Nothing is logged unless PES6_TRACE_IO / PES6_TRACE_GE is explicitly set.
The script only patches open-source host code; game files stay local/private.
"""
import argparse
from pathlib import Path


def once(s: str, anchor: str, replacement: str, label: str) -> str:
    if replacement in s:
        return s
    if s.count(anchor) != 1:
        raise RuntimeError(f"{label}: incompatible upstream source")
    return s.replace(anchor, replacement, 1)


def plan_io(s: str) -> tuple[str, bool]:
    if '[io-trace]' in s:
        if all(x in s for x in (
            'log_io("open-async",', 'log_io("read-async",',
            'log_io("ioctl",', 'log_io("devctl",', 'log_io("read",'
        )):
            return s, False
        raise RuntimeError("Partial I/O diagnostics patch")
    old = s
    s = once(s, '#include <cstring>\n',
             '#include <cstring>\n#include <cstdlib>\n', "include cstdlib")
    s = once(s, 'constexpr std::uint64_t kMaxWholeFileRead = 256u << 20u;\n',
             '''constexpr std::uint64_t kMaxWholeFileRead = 256u << 20u;

bool trace_io() {
    static const bool on = std::getenv("PES6_TRACE_IO") != nullptr;
    return on;
}
void log_io(const char *event, const std::string &path, std::int64_t number) {
    if (!trace_io()) return;
    static unsigned total = 0;
    if (total++ >= 180) return;
    std::cerr << "[io-trace] " << event << " path=" << path << " value=" << number << "\\n";
}
''', "trace helper")
    s = once(s,
        '    files_[fd] = OpenFile{file, nullptr, 0u, psp_path};\n    finish(ctx, static_cast<std::uint32_t>(fd));',
        '    files_[fd] = OpenFile{file, nullptr, 0u, psp_path};\n'
        '    log_io("open", psp_path, fd);\n'
        '    finish(ctx, static_cast<std::uint32_t>(fd));', "sync open")
    s = once(s,
        '    finish(ctx, static_cast<std::uint32_t>(std::fread(dst, 1u, ctx.gpr[6], it->second.file)));',
        '    const auto read = std::fread(dst, 1u, ctx.gpr[6], it->second.file);\n'
        '    log_io("read", it->second.path, static_cast<std::int64_t>(read));\n'
        '    finish(ctx, static_cast<std::uint32_t>(read));', "sync read")
    s = once(s,
        '    const bool ok = open.web != nullptr || open.file != nullptr;\n',
        '    const bool ok = open.web != nullptr || open.file != nullptr;\n'
        '    log_io("open-async", psp_path, ok ? fd : -1);\n', "async open")
    s = once(s,
        '    it->second.async_pending = false;\n    finish(ctx, 0u);\n}\n\nvoid Kernel::sceIoLseekAsync',
        '    it->second.async_pending = false;\n'
        '    log_io("read-async", it->second.path, it->second.async_result);\n'
        '    finish(ctx, 0u);\n}\n\nvoid Kernel::sceIoLseekAsync', "async read")
    s = once(s,
        '    const auto command = ctx.gpr[5];\n    if (device != "fatms0:")',
        '    const auto command = ctx.gpr[5];\n'
        '    log_io("devctl", device, static_cast<std::int64_t>(command));\n'
        '    if (device != "fatms0:")', "device controls")
    s = once(s,
        '    if (command == 0x04100002u) { // where the PGD container starts inside the file',
        '    log_io("ioctl", it->second.path, static_cast<std::int64_t>(command));\n'
        '    if (command == 0x04100002u) { // where the PGD container starts inside the file',
        "file controls")
    return s, old != s


def plan_ge(s: str) -> tuple[str, bool]:
    if '[ge-prim]' in s:
        if 'PES6_TRACE_GE' not in s:
            raise RuntimeError("Partial GE diagnostics patch")
        return s, False
    old = s
    needle = "void Ge::draw_primitive(std::uint32_t type, std::uint32_t count) {\n    ++stats_.prims;\n"
    replacement = """void Ge::draw_primitive(std::uint32_t type, std::uint32_t count) {
    ++stats_.prims;
    static const bool kTrace = std::getenv("PES6_TRACE_GE") != nullptr;
    if (kTrace) {
        static std::uint32_t printed = 0u;
        if (printed < 18u) {
            ++printed;
            std::cerr << "[ge-prim] frame=" << frame_ << " pc=0x" << std::hex << pc_
                      << " fb=0x" << regs_[kFrameBufPtr] << std::dec
                      << " type=" << type << " count=" << count
                      << " clear=" << (regs_[kClearMode] & 1u)
                      << " tex=" << (regs_[kTextureEnable] & 1u)
                      << " texaddr=0x" << std::hex << regs_[kTexAddr0] << std::dec << "\\n";
        }
    }
"""
    s = once(s, needle, replacement, "GE primitive")
    return s, old != s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    host = args.checkout / "PSPRecomp/profiles/web/host"
    io_file, ge_file = host / "io.cpp", host / "ge.cpp"
    new_io, io_changed = plan_io(io_file.read_text())
    new_ge, ge_changed = plan_ge(ge_file.read_text())
    if io_changed:
        io_file.write_text(new_io)
    if ge_changed:
        ge_file.write_text(new_ge)
    print("Private PSP diagnostic hooks:", "applied" if io_changed or ge_changed else "already applied")


if __name__ == "__main__":
    main()
