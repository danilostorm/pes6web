#!/usr/bin/env python3
"""Idempotent source-only patch: scan bounded executable ranges for fallthrough
entrypoints after PSP MIPS J/JR instructions, which can be indirect targets.

Controls: PSPRECOMP_FALLTHROUGH_RANGES='0x088c0000-0x088c5000,...'
This is opt-in to avoid exploding function discovery across the whole ISO.
"""
from pathlib import Path
import argparse

ANCHOR = "    program.functions.reserve(program.seeds.size());\n"
INSERT = """    // Opt-in: additional starts immediately after terminal J/JR delay slots.
    // PSP retail titles can reach these through computed jump tables.
    // Restrict scan to user-designated executable ranges; do not scan data.
    if (const char *extra_ranges = std::getenv("PSPRECOMP_FALLTHROUGH_RANGES")) {
        std::istringstream input(extra_ranges);
        for (std::string range; std::getline(input, range, ',');) {
            const auto dash = range.find('-');
            if (dash == std::string::npos)
                throw std::runtime_error("Invalid PSPRECOMP_FALLTHROUGH_RANGES entry: " + range);
            std::size_t used_lo = 0u, used_hi = 0u;
            const auto lo = std::stoull(range.substr(0, dash), &used_lo, 0);
            const auto hi = std::stoull(range.substr(dash + 1u), &used_hi, 0);
            if (used_lo != dash || used_hi != range.size() - dash - 1u ||
                lo > 0xFFFFFFFFull || hi > 0x100000000ull ||
                (lo & 3ull) != 0ull || (hi & 3ull) != 0ull ||
                lo >= hi || hi - lo > 0x100000ull)
                throw std::runtime_error("Invalid PSPRECOMP_FALLTHROUGH_RANGES bounds: " + range);
            for (std::uint64_t pc64 = lo; pc64 + 8ull < hi; pc64 += 4ull) {
                const auto pc = static_cast<std::uint32_t>(pc64);
                if (!is_executable_address(program.executable_ranges, pc)) continue;
                const auto decoded = decode_allegrex(memory.load32(pc));
                if (decoded.kind == OpcodeKind::J || decoded.kind == OpcodeKind::Jr)
                    add_seed(program.seeds, program.executable_ranges, pc + 8u,
                             "indirect_jr_or_j_fallthrough");
            }
        }
    }
"""


def plan(source: str) -> tuple[str, bool]:
    if "indirect_jr_or_j_fallthrough" in source:
        if INSERT not in source:
            raise RuntimeError("Partial fallthrough patch detected")
        return source, False
    if source.count(ANCHOR) != 1:
        raise RuntimeError("PSPRecomp changed; expected exactly one anchor")
    if '#include <sstream>' not in source or '#include <cstdlib>' not in source:
        raise RuntimeError("Apply patch_psp_extra_seeds.py first")
    return source.replace(ANCHOR, INSERT + ANCHOR, 1), True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    source = args.checkout / "PSPRecomp/src/program_analysis.cpp"
    new_text, changed = plan(source.read_text())
    if changed:
        source.write_text(new_text)
    print("PSP post-J/JR bounded CFG fallthrough patch:", "applied" if changed else "already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
