#!/usr/bin/env python3
"""Opt-in native ISO-backed PSP sce_lbn0x..._size0x... reads.

Only patches the pinned open-source PSPWeb HLE. No ISO, executable, or
copyrighted game data is read by this patcher or added to the repository.
At runtime the user supplies PES6_DISC_ISO=/path/to/their/disc.iso.
Browser builds retain their existing streamed-file behavior.
"""
import argparse
from pathlib import Path


def once(text: str, old: str, new: str, name: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{name}: upstream changed or partial patch ({text.count(old)} matches)")
    return text.replace(old, new, 1)


def once_in_function(text: str, signature: str, next_signature: str,
                     old: str, new: str, name: str) -> str:
    """Replace within one pinned HLE function, never matching an adjacent one."""
    if text.count(signature) != 1 or text.count(next_signature) != 1:
        raise RuntimeError(f"{name}: missing or ambiguous function boundary")
    begin = text.index(signature)
    end = text.index(next_signature, begin + len(signature))
    segment = text[begin:end]
    if segment.count(old) != 1:
        raise RuntimeError(f"{name}: upstream changed ({segment.count(old)} matches)")
    return text[:begin] + segment.replace(old, new, 1) + text[end:]


RAW_HELPER = r'''
// PES6_RAW_LBN_IO: native-only, bounded raw UMD sector file windows.
// The PSP pseudo-file path is disc0:/sce_lbn0x<sector>_size0x<bytes>.
bool parse_raw_sector(const std::string &path, std::uint64_t &base, std::uint64_t &length) {
    std::string lower = path;
    std::transform(lower.begin(), lower.end(), lower.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    std::string_view prefix;
    if (lower.rfind("disc0:/sce_lbn0x", 0) == 0) prefix = "disc0:/sce_lbn0x";
    else if (lower.rfind("umd0:/sce_lbn0x", 0) == 0) prefix = "umd0:/sce_lbn0x";
    else return false;
    const auto split = lower.find("_size0x", prefix.size());
    if (split == std::string::npos) return false;
    const std::string_view sectors(lower.data() + prefix.size(), split - prefix.size());
    const std::string_view bytes(lower.data() + split + 7, lower.size() - split - 7);
    if (sectors.empty() || bytes.empty()) return false;
    std::uint64_t sector = 0u;
    const auto p = std::from_chars(sectors.data(), sectors.data() + sectors.size(), sector, 16);
    const auto q = std::from_chars(bytes.data(), bytes.data() + bytes.size(), length, 16);
    if (p.ec != std::errc{} || p.ptr != sectors.data() + sectors.size() ||
        q.ec != std::errc{} || q.ptr != bytes.data() + bytes.size() ||
        length == 0u || sector > std::numeric_limits<std::uint64_t>::max() / 2048u)
        return false;
    base = sector * 2048u;
    return true;
}

bool open_raw_sector_file(const std::string &path, OpenFile &open) {
#if defined(__EMSCRIPTEN__)
    (void)path;
    (void)open;
    return false;
#else
    std::uint64_t base = 0u, length = 0u;
    if (!parse_raw_sector(path, base, length)) return false;
    const char *iso = std::getenv("PES6_DISC_ISO");
    if (iso == nullptr || *iso == '\0') return false;
    std::FILE *file = std::fopen(iso, "rb");
    if (file == nullptr) return false;
    if (std::fseek(file, 0, SEEK_END) != 0) {
        std::fclose(file);
        return false;
    }
    const long end = std::ftell(file);
    if (end < 0 || base > static_cast<std::uint64_t>(end) ||
        length > static_cast<std::uint64_t>(end) - base ||
        base > static_cast<std::uint64_t>(std::numeric_limits<long>::max())) {
        std::fclose(file);
        return false;
    }
    open.file = file;
    open.raw_lbn = true;
    open.raw_base = base;
    open.raw_length = length;
    return true;
#endif
}
'''


RAW_READ = r'''
std::uint32_t Kernel::raw_sector_read(OpenFile &open, std::uint32_t buffer, std::uint32_t length) {
    // Position is relative to the requested pseudo-file window, not the ISO.
    const auto remaining = open.position < open.raw_length ? open.raw_length - open.position : 0u;
    const auto count = static_cast<std::uint32_t>(std::min<std::uint64_t>(length, remaining));
    if (count == 0u) return 0u;
    auto *dst = rt_.memory().raw_pointer(buffer, count);
    if (dst == nullptr || open.file == nullptr) return kErrorBadFile;
    const auto absolute = open.raw_base + open.position;
    if (absolute > static_cast<std::uint64_t>(std::numeric_limits<long>::max()) ||
        std::fseek(open.file, static_cast<long>(absolute), SEEK_SET) != 0)
        return kErrorIo;
    const auto read = std::fread(dst, 1u, count, open.file);
    if (read < count && std::ferror(open.file)) return kErrorIo;
    open.position += read;
    log_io("read-raw", open.path, static_cast<std::int64_t>(read));
    return static_cast<std::uint32_t>(read);
}

'''


def plan(header: str, io: str) -> tuple[str, str, bool]:
    if "PES6_RAW_LBN_IO" in io:
        if ("bool raw_lbn{};" not in header or
                "Kernel::raw_sector_read(" not in io or
                io.count("PES6_RAW_LBN_IO") != 1):
            raise RuntimeError("Partial raw sector patch")
        return header, io, False
    header = once(header, "    std::uint32_t pgd_offset{};",
                  "    std::uint64_t raw_base{}; // ISO byte offset\n"
                  "    std::uint64_t raw_length{}; // bounded virtual file size\n"
                  "    bool raw_lbn{};\n"
                  "    std::uint32_t pgd_offset{};", "OpenFile state")
    header = once(header, "    std::uint32_t plain_read(OpenFile &open, std::uint32_t buffer, std::uint32_t length);",
                  "    std::uint32_t raw_sector_read(OpenFile &open, std::uint32_t buffer, std::uint32_t length);\n"
                  "    std::uint32_t plain_read(OpenFile &open, std::uint32_t buffer, std::uint32_t length);",
                  "raw read declaration")
    io = once(io, "#include <algorithm>\n",
              "#include <algorithm>\n#include <charconv>\n#include <limits>\n#include <string_view>\n", "parser includes")
    io = once(io, "} // namespace\n\nvoid webfs_native_poll(WebFs &fs);",
              RAW_HELPER + "\n} // namespace\n\nvoid webfs_native_poll(WebFs &fs);", "raw helper")
    io = once(io,
              "    std::FILE *file = std::fopen(host_path(psp_path).string().c_str(), fopen_mode(ctx.gpr[5]));\n",
              "    OpenFile raw{nullptr, nullptr, 0u, psp_path};\n"
              "    if (open_raw_sector_file(psp_path, raw)) {\n"
              "        const std::int32_t fd = next_fd_++;\n"
              "        files_[fd] = std::move(raw);\n"
              "        log_io(\"open-raw\", psp_path, fd);\n"
              "        finish(ctx, static_cast<std::uint32_t>(fd));\n"
              "        return;\n"
              "    }\n"
              "    std::FILE *file = std::fopen(host_path(psp_path).string().c_str(), fopen_mode(ctx.gpr[5]));\n",
              "sync open")
    io = once(io,
              "    if (it->second.plain) {\n        finish(ctx, plain_read(it->second, ctx.gpr[5], ctx.gpr[6]));",
              "    if (it->second.raw_lbn) {\n"
              "        finish(ctx, raw_sector_read(it->second, ctx.gpr[5], ctx.gpr[6]));\n"
              "        return;\n"
              "    }\n"
              "    if (it->second.plain) {\n        finish(ctx, plain_read(it->second, ctx.gpr[5], ctx.gpr[6]));",
              "sync read")
    io = once_in_function(io, "void Kernel::sceIoLseek(Ctx &ctx) {",
              "void Kernel::sceIoLseek32(Ctx &ctx) {",
              "    if (it != files_.end() && (it->second.plain || it->second.web != nullptr)) {",
              "    if (it != files_.end() && it->second.raw_lbn) {\n"
              "        it->second.position = std::min(it->second.raw_length,\n"
              "            seek_target(it->second.position, it->second.raw_length, offset, ctx.gpr[8]));\n"
              "        finish64(ctx, it->second.position);\n"
              "        return;\n"
              "    }\n"
              "    if (it != files_.end() && (it->second.plain || it->second.web != nullptr)) {",
              "64-bit seek")
    io = once_in_function(io, "void Kernel::sceIoLseek32(Ctx &ctx) {",
              "void Kernel::sceIoGetstat(Ctx &ctx) {",
              "    if (it != files_.end() && (it->second.plain || it->second.web != nullptr)) {",
              "    if (it != files_.end() && it->second.raw_lbn) {\n"
              "        it->second.position = std::min(it->second.raw_length,\n"
              "            seek_target(it->second.position, it->second.raw_length, offset, ctx.gpr[6]));\n"
              "        finish(ctx, static_cast<std::uint32_t>(it->second.position));\n"
              "        return;\n"
              "    }\n"
              "    if (it != files_.end() && (it->second.plain || it->second.web != nullptr)) {",
              "32-bit seek")
    io = once(io,
              "    if (webfs_ && disc_relative(psp_path, relative)) {\n"
              "        const WebFile *file = webfs_->find(relative);\n"
              "        open.web = file != nullptr && !file->directory ? file : nullptr;\n"
              "    } else {\n"
              "        open.file = std::fopen(host_path(psp_path).string().c_str(), fopen_mode(ctx.gpr[5]));\n"
              "    }\n",
              "    if (!open_raw_sector_file(psp_path, open)) {\n"
              "        if (webfs_ && disc_relative(psp_path, relative)) {\n"
              "            const WebFile *file = webfs_->find(relative);\n"
              "            open.web = file != nullptr && !file->directory ? file : nullptr;\n"
              "        } else {\n"
              "            open.file = std::fopen(host_path(psp_path).string().c_str(), fopen_mode(ctx.gpr[5]));\n"
              "        }\n"
              "    }\n",
              "async open")
    io = once(io,
              "    if (it->second.plain) {\n        it->second.async_result = static_cast<std::int32_t>(plain_read(it->second, ctx.gpr[5], ctx.gpr[6]));",
              "    if (it->second.raw_lbn) {\n"
              "        it->second.async_result = static_cast<std::int32_t>(raw_sector_read(it->second, ctx.gpr[5], ctx.gpr[6]));\n"
              "        it->second.async_pending = false;\n"
              "        finish(ctx, 0u);\n"
              "        return;\n"
              "    }\n"
              "    if (it->second.plain) {\n        it->second.async_result = static_cast<std::int32_t>(plain_read(it->second, ctx.gpr[5], ctx.gpr[6]));",
              "async read")
    io = once(io,
              "    if (it->second.plain || it->second.web != nullptr) {\n",
              "    if (it->second.raw_lbn) {\n"
              "        it->second.position = std::min(it->second.raw_length,\n"
              "            seek_target(it->second.position, it->second.raw_length, offset, ctx.gpr[8]));\n"
              "        it->second.async_result = static_cast<std::int64_t>(it->second.position);\n"
              "    } else if (it->second.plain || it->second.web != nullptr) {\n",
              "async seek")
    io = once(io,
              "std::uint32_t Kernel::plain_read(OpenFile &open, std::uint32_t buffer, std::uint32_t length) {",
              RAW_READ + "std::uint32_t Kernel::plain_read(OpenFile &open, std::uint32_t buffer, std::uint32_t length) {",
              "raw read implementation")
    return header, io, True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("checkout", type=Path)
    args = p.parse_args()
    base = args.checkout / "PSPRecomp/profiles/web/host"
    hpath, ipath = base / "kernel.hpp", base / "io.cpp"
    header, io, changed = plan(hpath.read_text(), ipath.read_text())
    if changed:
        hpath.write_text(header)
        ipath.write_text(io)
    print("PSP raw ISO LBN HLE:", "installed" if changed else "already installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
