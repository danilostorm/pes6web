# PES6Web build / bring-up status

Last evaluated: 2026-10-11. No playable runtime has been demonstrated.

| Gate | Status | Evidence / next step |
| --- | --- | --- |
| Confirm game files | DONE | EU ISO, extracted PSP_GAME assets available in user's Drive (not committed) |
| Identify executable | DONE | `EBOOT.BIN` is a `~PSP` encrypted module; `BOOT.BIN` is zero-filled |
| Inspector + unit tests | DONE | `tools/inspect_psp.py`, standard-library test suite |
| Recomp toolchain wrapper | CREATED / UNTESTED ON GAME | `scripts/bootstrap.sh`, `scripts/port.sh` wrap upstream toolchain |
| Decrypt retail executable | BLOCKED | Requires running external `pspdecrypt` or a private decrypted ELF |
| Generate C++ from actual PES6 ELF | NOT YET RUN | Run toolchain with decrypted ELF |
| Compile native / Wasm | NOT YET RUN | Run `scripts/port.sh ... --native` |
| Menus rendered | NOT YET VERIFIED | Native frame dump then browser check |
| Match in-game | NOT YET VERIFIED | Select teams, start match, render players/ball |
| Keyboard/gamepad/mobile touch | NOT YET VERIFIED | End-to-end browser hardware tests |
| Unraid deployment | CONFIG ONLY | `compose.yaml`, `deploy/nginx.conf` (serve after actual build) |

## Focused debugging loop

1. Build with `--native` and keep `work/logs/port-*.log`.
2. Inspect first exact failure: `No recompiled function registered`, unimplemented HLE, filesystem failure, or GE draw failure.
3. Add reproducible tests or trace assertions *before* changes to upstream runtime.
4. Apply minimal game-specific changes as patches under this project (future milestone), rather than copying proprietary generated code into Git.
5. Iterate to a stable menu, then to a complete match. Record actual tested browser/hardware FPS, not estimates.

The previously reported guest address `0x089864D0` is a **lead** from an earlier experiment, not a diagnosis. The exact plain ELF and backtrace are needed to identify the missing dispatch entry.
