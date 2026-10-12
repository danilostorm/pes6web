#!/usr/bin/env python3
"""Optional PSP raw ISO async-read latency experiment on the CPU scheduler.

With PES6_RAW_ASYNC_DEFER=1, complete raw-sector reads on the following
emulated host frame. Default I/O behavior remains unchanged. The guest
buffer is filled only when the operation completes.
"""
import argparse
from pathlib import Path


def once(src, anchor, replacement, name):
    if src.count(anchor) != 1:
        raise RuntimeError(f"{name}: incompatible pinned source ({src.count(anchor)} matches)")
    return src.replace(anchor, replacement, 1)


def plan(header, io):
    marker = "PES6_RAW_ASYNC_DEFER"
    if marker in io:
        if io.count(marker) < 1 or "raw_async_scheduled" not in header or "read-raw-complete" not in io:
            raise RuntimeError("Partial deferred PSP raw read patch")
        return header, io, False
    original = (header, io)
    header = once(header,
                  "    bool raw_lbn{};\n",
                  """    bool raw_lbn{};
    bool raw_async_scheduled{};
    std::uint32_t raw_async_buffer{};
    std::uint32_t raw_async_length{};
    std::uint32_t raw_async_due_frame{};
""", "OpenFile raw asynchronous state")
    io = once(io,
              """void Kernel::poll_io() {
#if !defined(__EMSCRIPTEN__)
    if (webfs_) webfs_native_poll(*webfs_);
#endif
}
""",
              """void Kernel::poll_io() {
#if !defined(__EMSCRIPTEN__)
    if (webfs_) webfs_native_poll(*webfs_);
    // Complete only raw-sector operations whose virtual latency elapsed.
    // Collect IDs first because finish_async may delete a closing descriptor.
    std::vector<std::int32_t> ready;
    for (const auto &[fd, open] : files_) {
        if (open.raw_async_scheduled && open.raw_async_due_frame <= display_.vcount)
            ready.push_back(fd);
    }
    for (const auto fd : ready) {
        const auto it = files_.find(fd);
        if (it == files_.end()) continue;
        auto &open = it->second;
        const auto result = raw_sector_read(open, open.raw_async_buffer, open.raw_async_length);
        open.async_result = static_cast<std::int32_t>(result);
        open.raw_async_scheduled = false;
        open.async_pending = false;
        log_io("read-raw-complete", open.path, open.async_result);
        finish_async(fd);
    }
#endif
}
""", "frame-bounded PSP raw async completion")
    io = once(io,
              """    if (it->second.raw_lbn) {
        it->second.async_result = static_cast<std::int32_t>(raw_sector_read(it->second, ctx.gpr[5], ctx.gpr[6]));
        it->second.async_pending = false;
        finish(ctx, 0u);
        return;
    }
""",
              """    if (it->second.raw_lbn) {
        // PES6_RAW_ASYNC_DEFER: timing compatibility experiment, opt in only.
        if (std::getenv("PES6_RAW_ASYNC_DEFER") != nullptr) {
            if (it->second.async_pending) {
                finish(ctx, kErrorIo);
                return;
            }
            it->second.raw_async_buffer = ctx.gpr[5];
            it->second.raw_async_length = ctx.gpr[6];
            it->second.raw_async_due_frame = display_.vcount + 1u;
            it->second.raw_async_scheduled = true;
            it->second.async_pending = true;
            log_io("read-raw-queued", it->second.path, ctx.gpr[6]);
            finish(ctx, 0u);
            return;
        }
        it->second.async_result = static_cast<std::int32_t>(raw_sector_read(it->second, ctx.gpr[5], ctx.gpr[6]));
        it->second.async_pending = false;
        finish(ctx, 0u);
        return;
    }
""", "async raw-sector read opt-in latency")
    return header, io, (header, io) != original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    host = args.checkout / "PSPRecomp/profiles/web/host"
    hfile, ifile = host / "kernel.hpp", host / "io.cpp"
    header, io, changed = plan(hfile.read_text(), ifile.read_text())
    if changed:
        hfile.write_text(header)
        ifile.write_text(io)
    print("Optional raw ISO asynchronous read latency:", "installed" if changed else "already installed")


if __name__ == "__main__":
    main()
