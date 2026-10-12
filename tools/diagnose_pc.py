#!/usr/bin/env python3
"""Inspect where a halted PSP guest PC maps into a local, private ELF.

Never uploads the ELF or generated game code. Prints only local offset/mapping,
a few MIPS words, and whether labels for the target exist in generated C++.
"""
from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path

LOAD_BASE = 0x08804000
ET_SCE_PRX = 0xFFA0


def parse_load_segments(blob: bytes) -> tuple[int, list[tuple[int, int, int, int]]]:
    if len(blob) < 52 or blob[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Expected 32-bit, little-endian ELF")
    etype, machine = struct.unpack_from("<HH", blob, 16)
    if machine != 8:
        raise ValueError("ELF machine is not MIPS")
    phoff = struct.unpack_from("<I", blob, 28)[0]
    phentsize, phnum = struct.unpack_from("<HH", blob, 42)
    if phnum > 128 or phentsize < 32 or phoff + phentsize * phnum > len(blob):
        raise ValueError("Invalid program header bounds")
    segs = []
    for i in range(phnum):
        ptype, off, va, _, size, memsz = struct.unpack_from("<IIIIII", blob, phoff + i * phentsize)
        if ptype != 1:
            continue
        if size > memsz or off + size > len(blob):
            raise ValueError("Invalid PT_LOAD bounds")
        runtime_va = LOAD_BASE + va if etype == ET_SCE_PRX else va
        segs.append((runtime_va, off, size, memsz))
    return etype, segs


def address_info(blob: bytes, address: int) -> dict[str, object]:
    etype, segs = parse_load_segments(blob)
    for va, off, size, memsz in segs:
        if va <= address < va + memsz:
            delta = address - va
            result: dict[str, object] = {
                "addr": f"0x{address:08X}",
                "segment_start": f"0x{va:08X}",
                "segment_end": f"0x{va + memsz:08X}",
                "elf_file_offset": f"0x{off + delta:X}" if delta < size else None,
                "in_file": delta < size,
                "type": f"0x{etype:04X}",
            }
            if delta < size:
                word_start = max(0, delta - 4 * 4)
                word_end = min(size, delta + 5 * 4)
                words = []
                for d in range((word_start + 3) & ~3, word_end, 4):
                    if d + 4 > size:
                        break
                    ins = struct.unpack_from("<I", blob, off + d)[0]
                    words.append((f"0x{va + d:08X}", f"0x{ins:08X}"))
                result["words"] = words
            return result
    return {"addr": f"0x{address:08X}", "mapped": False}


def generated_mentions(folder: Path, address: int, max_files: int = 8) -> list[tuple[str, int, str]]:
    labels = {f"L_{address:08X}", f"0x{address:08X}", f"0x{address:08x}"}
    hits = []
    if not folder.is_dir():
        return hits
    for f in sorted(folder.glob("generated_*.cpp")):
        with f.open("r", encoding="utf-8", errors="replace") as stream:
            for number, line in enumerate(stream, 1):
                if any(label in line for label in labels):
                    # No proprietary generated code line is printed.
                    marker = "label" if f"L_{address:08X}" in line else "address"
                    hits.append((f.name, number, marker))
                    if len(hits) >= max_files:
                        return hits
    return hits


def inspect(elf: Path, folder: Path, addresses: list[int]) -> str:
    blob = elf.read_bytes()
    parse_load_segments(blob)
    lines = [f"ELF valid: size={len(blob)} bytes; generated units directory exists={folder.is_dir()}"]
    for address in addresses:
        info = address_info(blob, address)
        lines.append(f"\nGuest PC: 0x{address:08X}")
        if not info.get("mapped", True):
            lines.append("  OUTSIDE PT_LOAD segments; check guest dispatch or dynamic code")
            continue
        lines.append(f"  module segment: {info['segment_start']} .. {info['segment_end']}")
        lines.append(f"  ELF file offset: {info['elf_file_offset'] or 'zero-fill only (BSS)'}")
        for pc, instr in info.get("words", []):
            lines.append(f"  {'>>' if int(pc, 16) == address else '  '} {pc}: {instr}")
        hits = generated_mentions(folder, address)
        lines.append("  Generated C++ mentions (file:line; no source printed):")
        if not hits:
            lines.append("    no direct label/address found")
        else:
            lines.extend(f"    {filename}:{num} ({kind})" for filename, num, kind in hits)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--address", action="append", required=True, help="Guest PC, e.g. 0x0897FD08")
    args = parser.parse_args()
    addresses = [int(x, 0) for x in args.address]
    for a in addresses:
        if a < 0 or a > 0xFFFFFFFF or a % 4:
            parser.error("Addresses must be aligned 32-bit guest addresses")
    print(inspect(args.elf, args.generated, addresses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
