#!/usr/bin/env python3
"""Inspect a locally owned PSP dump. Never uploads or modifies any game data.

stdlib only; usable with an extracted PSP_GAME folder or individual files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def decode_sfo(data: bytes) -> dict[str, str | int]:
    if len(data) < 20 or data[:4] != b'\x00PSF':
        raise ValueError('invalid PARAM.SFO signature')
    _, _, keys_offset, values_offset, count = struct.unpack_from('<5I', data, 0)
    if count > 4096 or 20 + count * 16 > len(data):
        raise ValueError('invalid PARAM.SFO item count')
    if keys_offset >= len(data) or values_offset >= len(data):
        raise ValueError('invalid PARAM.SFO table offset')
    result: dict[str, str | int] = {}
    for i in range(count):
        key_off, fmt, size, capacity, value_off = struct.unpack_from('<HHIII', data, 20 + i * 16)
        start = keys_offset + key_off
        if start >= len(data) or size > capacity or values_offset + value_off + size > len(data):
            raise ValueError(f'invalid PARAM.SFO entry {i}')
        key_end = data.find(b'\0', start, min(len(data), start + 256))
        if key_end < 0:
            raise ValueError(f'unterminated PARAM.SFO key {i}')
        key = data[start:key_end].decode('ascii', 'replace')
        value = data[values_offset + value_off:values_offset + value_off + size]
        if fmt == 0x0404 and size >= 4:
            result[key] = struct.unpack_from('<I', value)[0]
        elif fmt in (0x0004, 0x0204):
            result[key] = value.rstrip(b'\0').decode('utf-8', 'replace')
        else:
            result[key] = f'unknown_format_0x{fmt:04x}'
    return result


def elf_info(data: bytes) -> dict:
    if len(data) < 52 or data[:4] != b'\x7fELF':
        raise ValueError('not an ELF file')
    if data[4] != 1 or data[5] != 1:
        raise ValueError('not a 32-bit little endian ELF')
    e_machine = struct.unpack_from('<H', data, 18)[0]
    entry = struct.unpack_from('<I', data, 24)[0]
    return {'architecture': 'MIPS' if e_machine == 8 else f'machine_{e_machine}',
            'entry_point': f'0x{entry:08X}', 'is_psp_compatible': e_machine == 8}


def inspect_file(path: Path) -> dict:
    if not path.is_file():
        return {'status': 'missing'}
    raw = path.read_bytes()
    result: dict = {'status': 'unknown', 'size': len(raw),
                    'sha256': hashlib.sha256(raw).hexdigest()}
    if not raw:
        result['status'] = 'empty'
    elif not any(raw):
        result['status'] = 'zero_filled'
    elif raw.startswith(b'~PSP'):
        result['status'] = 'encrypted_psp'
        if len(raw) >= 0xD4:
            result['kirk_tag'] = f'0x{struct.unpack_from("<I", raw, 0xD0)[0]:08X}'
    elif raw.startswith(b'\x7fELF'):
        try:
            result['elf'] = elf_info(raw)
            result['status'] = 'elf'
        except ValueError as exc:
            result['status'] = 'invalid_elf'
            result['error'] = str(exc)
    elif raw.startswith(b'\x00PSF'):
        try:
            result['sfo'] = decode_sfo(raw)
            result['status'] = 'sfo'
        except ValueError as exc:
            result['status'] = 'invalid_sfo'
            result['error'] = str(exc)
    return result


def resolve_root(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.name == 'PSP_GAME':
        return path
    if (path / 'PSP_GAME').is_dir():
        return path / 'PSP_GAME'
    raise FileNotFoundError(f'expected PSP_GAME directory at {path}')


def analyze(path: Path) -> dict:
    root = resolve_root(path)
    files = {
        'EBOOT.BIN': inspect_file(root / 'SYSDIR' / 'EBOOT.BIN'),
        'BOOT.BIN': inspect_file(root / 'SYSDIR' / 'BOOT.BIN'),
        'PARAM.SFO': inspect_file(root / 'PARAM.SFO'),
    }
    eboot = files['EBOOT.BIN']['status']
    boot = files['BOOT.BIN']['status']
    actions = []
    if eboot == 'encrypted_psp' and boot != 'elf':
        actions.append('Decrypt EBOOT.BIN with pspdecrypt, or provide a decrypted MIPS ELF from your own dump.')
    elif eboot == 'elf':
        actions.append('EBOOT.BIN is a plain ELF; ready for recompiler validation.')
    elif boot == 'elf':
        actions.append('BOOT.BIN is a plain ELF; confirm which executable to use.')
    else:
        actions.append('No usable PSP executable found; verify the dump.')
    if boot == 'zero_filled':
        actions.append('BOOT.BIN contains only zeros; do not feed it to the recompiler.')
    sfo = files['PARAM.SFO']
    if sfo['status'] != 'sfo':
        actions.append('PARAM.SFO is missing or invalid; verify the disc folder.')
    return {'platform': 'PSP', 'files': files, 'actions': actions,
            'ready_for_recompilation': eboot == 'elf' or boot == 'elf'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Inspect a PSP game dump without modifying it')
    parser.add_argument('disc', type=Path, help='Extracted disc folder or PSP_GAME directory')
    parser.add_argument('--json', action='store_true', help='Output machine-readable JSON')
    args = parser.parse_args(argv)
    try:
        report = analyze(args.disc)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('PSP GAME / EXE DIAGNOSTIC')
        for name, item in report['files'].items():
            print(f'  {name:<12} {item["status"]:<16} {item.get("size", "-")} bytes')
            if name == 'PARAM.SFO' and 'sfo' in item:
                for key in ('TITLE','DISC_ID','DISC_VERSION','PSP_SYSTEM_VER'):
                    if key in item['sfo']:
                        print(f'    {key}: {item["sfo"][key]}')
            if item.get('kirk_tag'):
                print('    PSP KIRK tag:', item['kirk_tag'])
        for line in report['actions']:
            print('  NEXT:', line)
        print('  Ready to recompile:', 'yes' if report['ready_for_recompilation'] else 'no')
    # A valid encrypted disc still yields 0: "not ready" is a result, not an inspection failure.
    return 0


if __name__ == '__main__':
    sys.exit(main())
