#!/usr/bin/env python3
"""Recover a single genuinely executable PSP ELF entry from a native boot halt.

Local-only: no game data is uploaded or printed. Cap all automatic additions,
reject BSS/data/duplicate PCs, and never interpret an arbitrary crash as success.
"""
from __future__ import annotations
import argparse
import re
import struct
from pathlib import Path

HALT = re.compile(r"(?:\[kernel\] halted:|\[pspweb\] guest stopped:).*?at (0x[0-9A-Fa-f]{8}): invalid internal function entry")


def candidate(log: str, elf: bytes) -> int:
    hits = HALT.findall(log)
    if not hits:
        raise ValueError("No invalid-internal-function-entry halt; manual investigation needed")
    addr = int(hits[-1], 16)
    if addr & 3 or addr < 0x08800000:
        raise ValueError("Guest PC is not a valid aligned user address")
    if elf[:6] != b"\x7fELF\x01\x01" or len(elf) < 52:
        raise ValueError("Expected little-endian 32-bit ELF")
    e_type, machine = struct.unpack_from("<HH", elf, 16)
    if machine != 8:
        raise ValueError("Expected MIPS ELF")
    phoff = struct.unpack_from("<I", elf, 28)[0]
    phentsize, phnum = struct.unpack_from("<HH", elf, 42)
    if phentsize < 32 or phnum > 128 or phoff + phentsize * phnum > len(elf):
        raise ValueError("Corrupt ELF program header table")
    for n in range(phnum):
        p_type, p_offset, p_vaddr, _, p_filesz, p_memsz, p_flags = struct.unpack_from(
            "<IIIIIII", elf, phoff + n * phentsize
        )
        if p_type != 1 or not (p_flags & 1):  # PT_LOAD with PF_X
            continue
        va = p_vaddr + (0x08804000 if e_type == 0xFFA0 else 0)
        if not (va <= addr <= va + p_filesz - 4) or p_offset + p_filesz > len(elf):
            continue
        instr = struct.unpack_from("<I", elf, p_offset + addr - va)[0]
        if instr == 0:
            raise ValueError("ELF entry points to a zero/NOP word")
        return addr
    raise ValueError("Guest PC not inside an on-disk executable PT_LOAD segment")


def add_seed(seed_path: Path, addr: int, limit: int = 1000) -> bool:
    previous = seed_path.read_text().strip() if seed_path.exists() else ""
    seeds = {int(token, 0) for token in previous.split(",") if token.strip()}
    if addr in seeds:
        return False
    if len(seeds) >= limit:
        raise ValueError("Maximum 1,000 recovered entry points reached")
    seeds.add(addr)
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    temp = seed_path.with_suffix(".tmp")
    temp.write_text(",".join(f"0x{entry:08X}" for entry in sorted(seeds)) + "\n")
    temp.replace(seed_path)
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--elf", type=Path, required=True)
    p.add_argument("--seeds", type=Path, required=True)
    args = p.parse_args()
    addr = candidate(args.log.read_text(errors="replace"), args.elf.read_bytes())
    if not add_seed(args.seeds, addr):
        print(f"ALREADY_KNOWN 0x{addr:08X}: requires control-flow/HLE investigation")
        return 3
    print(f"RECOVERED 0x{addr:08X}: verified in executable ELF; private seed list updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
