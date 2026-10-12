#!/usr/bin/env python3
"""Opt-in PSP graphics-command event trace, without changing guest behavior.

PES6_TRACE_GE_EVENTS=1 reports bounded FINISH/SIGNAL/END instructions and
display-list starts to distinguish GPU callback synchronization from a
repeated frame clear. The trace never includes commercial game content.
"""
from pathlib import Path
import argparse


def once(source: str, anchor: str, replacement: str, context: str) -> str:
    if replacement in source:
        return source
    if source.count(anchor) != 1:
        raise RuntimeError(f"{context}: pinned upstream source changed")
    return source.replace(anchor, replacement, 1)


def plan(ge_cpp: str) -> tuple[str, bool]:
    if "PES6_TRACE_GE_EVENTS" in ge_cpp:
        if (ge_cpp.count("[ge-event]") != 2 or
                "[ge-list]" not in ge_cpp or "kTraceGeEvents" not in ge_cpp):
            raise RuntimeError("Partially patched graphics event diagnostics")
        return ge_cpp, False
    original = ge_cpp
    ge_cpp = once(
        ge_cpp,
        "    ++stats_.lists;\n    pc_ = start & 0x0FFFFFFFu;\n",
        """    ++stats_.lists;
    static const bool kTraceGeEvents = std::getenv("PES6_TRACE_GE_EVENTS") != nullptr;
    if (kTraceGeEvents) {
        static std::uint32_t printed_lists = 0u;
        if (printed_lists++ < 12u)
            std::cerr << "[ge-list] frame=" << frame_ << " start=0x" << std::hex
                      << start << " stall=0x" << stall << std::dec << "\\n";
    }
    pc_ = start & 0x0FFFFFFFu;
""",
        "display-list start",
    )
    ge_cpp = once(
        ge_cpp,
        "        if ((op >> 24u) == kEnd) return true;\n",
        """        if ((op >> 24u) == kEnd) {
            if (kTraceGeEvents) {
                static std::uint32_t ends = 0u;
                if (ends++ < 24u)
                    std::cerr << "[ge-event] frame=" << frame_ << " END pc=0x"
                              << std::hex << (pc_ - 4u) << std::dec << "\\n";
            }
            return true;
        }
""",
        "display-list END",
    )
    ge_cpp = once(
        ge_cpp,
        "    const std::uint32_t data = op & 0x00FFFFFFu;\n    switch (cmd) {\n",
        """    const std::uint32_t data = op & 0x00FFFFFFu;
    if (std::getenv("PES6_TRACE_GE_EVENTS") != nullptr &&
        (cmd == 0x0Eu || cmd == kFinish)) {
        static std::uint32_t events = 0u;
        if (events++ < 36u)
            std::cerr << "[ge-event] frame=" << frame_ << (cmd == 0x0Eu ? " SIGNAL" : " FINISH")
                      << " pc=0x" << std::hex << (pc_ - 4u)
                      << " param=0x" << data << std::dec << "\\n";
    }
    switch (cmd) {
""",
        "SIGNAL and FINISH",
    )
    return ge_cpp, ge_cpp != original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    path = args.checkout / "PSPRecomp/profiles/web/host/ge.cpp"
    updated, changed = plan(path.read_text())
    if changed:
        path.write_text(updated)
    print("PSP GE event trace:", "installed" if changed else "already installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
