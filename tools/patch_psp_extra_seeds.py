#!/usr/bin/env python3
"""Opt-in, idempotent PSPRecomp CFG seed support for indirect guest targets.

Only edits open-source program_analysis.cpp in the private local checkout.
Never copies any retail code into Git.
"""
from pathlib import Path
import argparse

INCLUDES_ANCHOR = "#include <deque>\n"
INCLUDES = "#include <deque>\n#include <cstdlib>\n#include <sstream>\n#include <stdexcept>\n#include <string>\n"
SEED_ANCHOR = "    program.seeds = collect_initial_seeds(elf, memory, load_base, program.executable_ranges);\n"
SEED_REPLACEMENT = """    program.seeds = collect_initial_seeds(elf, memory, load_base, program.executable_ranges);
    // Additional verified executable entries (e.g. indirect function targets).
    // Only enabled when PSPRECOMP_EXTRA_SEEDS is supplied at code generation.
    if (const char *extra = std::getenv("PSPRECOMP_EXTRA_SEEDS")) {
        std::istringstream input(extra);
        for (std::string token; std::getline(input, token, ',');) {
            std::size_t used = 0;
            const auto number = std::stoull(token, &used, 0);
            if (used != token.size() || number > 0xFFFFFFFFull ||
                !is_executable_address(program.executable_ranges, static_cast<std::uint32_t>(number)))
                throw std::runtime_error("PSPRECOMP_EXTRA_SEEDS contains an invalid executable address: " + token);
            program.seeds.try_emplace(static_cast<std::uint32_t>(number), "configured_indirect_target");
        }
    }
"""


def plan(source: str) -> tuple[str, bool]:
    if '"configured_indirect_target"' in source:
        if INCLUDES not in source:
            raise RuntimeError("Partially patched upstream: missing includes")
        return source, False
    if source.count(SEED_ANCHOR) != 1 or source.count(INCLUDES_ANCHOR) != 1:
        raise RuntimeError("Upstream changed; cannot patch safely")
    source = source.replace(INCLUDES_ANCHOR, INCLUDES, 1)
    source = source.replace(SEED_ANCHOR, SEED_REPLACEMENT, 1)
    return source, True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    f = args.checkout / "PSPRecomp" / "src" / "program_analysis.cpp"
    original = f.read_text()
    updated, changed = plan(original)
    if changed:
        f.write_text(updated)
        print("Added PSPRECOMP_EXTRA_SEEDS to PSPRecomp CFG discovery")
    else:
        print("Additional seed patch already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
