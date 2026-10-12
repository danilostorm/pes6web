#!/usr/bin/env python3
"""Print native GE/GL counters at guest exit, including before frame 60.

Existing upstream runtime prints these stats only every 60 frames, masking
graphics diagnostics for titles that halt at boot frame 1.
"""
from pathlib import Path
import argparse

ANCHOR = '        std::cout << "[pspweb] ran " << frame << " frames, vcount="'
ADD = """        const auto &last_ge = g_session.kernel->ge().stats();
        std::cout << "[pspweb] ge-exit lists=" << last_ge.lists
                  << " prims=" << last_ge.prims << " triangles=" << last_ge.triangles
                  << " sprites=" << last_ge.sprites << " pixels=" << last_ge.pixels
                  << " transfers=" << last_ge.transfers
                  << " flips=" << g_session.kernel->display().flips << "\\n";
        if (g_session.gl)
            std::cout << "[pspweb] gl-exit draw_calls=" << g_session.gl->draw_calls()
                      << " uploads=" << g_session.gl->uploads()
                      << " downloads=" << g_session.gl->downloads() << "\\n";
"""


def plan(source: str) -> tuple[str, bool]:
    if ADD in source:
        return source, False
    if source.count(ANCHOR) != 1:
        raise RuntimeError("Unexpected native host runner source; refusing patch")
    return source.replace(ANCHOR, ADD + ANCHOR, 1), True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    source_file = args.checkout / "PSPRecomp/profiles/web/host/main.cpp"
    new_source, changed = plan(source_file.read_text())
    if changed:
        source_file.write_text(new_source)
    print("Native GE/GL diagnostic:", "applied" if changed else "already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
