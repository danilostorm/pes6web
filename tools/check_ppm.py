#!/usr/bin/env python3
"""Report RGB content in a native PSP frame capture; not a gameplay detector."""
from pathlib import Path
import argparse


def inspect_ppm(data: bytes) -> tuple[int, int, int, int]:
    parts = data.split(b"\n", 3)
    if len(parts) != 4 or parts[0] != b"P6" or parts[2] != b"255":
        raise ValueError("Expected P6 RGB24 PPM without comment headers")
    dimensions = parts[1].split()
    if len(dimensions) != 2:
        raise ValueError("Invalid PPM dimensions")
    width, height = map(int, dimensions)
    if width < 1 or height < 1 or width > 4096 or height > 4096:
        raise ValueError("Invalid image dimensions")
    rgb = parts[3]
    if len(rgb) != width * height * 3:
        raise ValueError("Unexpected RGB data length")
    nonblack = sum(rgb[i:i+3] != b"\x00\x00\x00" for i in range(0, len(rgb), 3))
    return width, height, nonblack, width * height


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    width, height, visible, count = inspect_ppm(args.capture.read_bytes())
    print(f"[frame-check] size={width}x{height} nonblack={visible}/{count} ({visible * 100 / count:.1f}%)")
    if visible == 0:
        print("[frame-check] ALL BLACK: framebuffer exists, but no visible game image yet.")
    else:
        print("[frame-check] Nonblack pixels found; menu/gameplay STILL requires visual verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
