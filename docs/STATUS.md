# PES6Web build / bring-up status

Last evaluated: 2026-10-11. No playable runtime has been demonstrated.

| Gate | Status | Evidence / next step |
| --- | --- | --- |
| Confirm game files | DONE | EU ISO, extracted PSP_GAME assets available in user's Drive (not committed) |
| Identify executable | DONE | `EBOOT.BIN` is a `~PSP` encrypted module; `BOOT.BIN` is zero-filled |
| Inspector + unit tests | DONE | `tools/inspect_psp.py`, standard-library test suite |
| Recomp toolchain wrapper | CREATED / UNTESTED ON GAME | `scripts/bootstrap.sh`, `scripts/port.sh` wrap upstream toolchain |
| Decrypt retail executable | DONE | AEROCOOL log: tag `C0CB167C` decrypted to a 1,914,920-byte ELF |
| Generate C++ from actual PES6 ELF | DONE | 6,757 seeds; 343,280 emitted PCs; 87,727 registered blocks; 117 units |
| Compile native / Wasm | DONE | Native and browser builds linked successfully on AEROCOOL; no gameplay confirmed |
| Native boot | NOT YET TESTED | Run `scripts/smoke-native.sh 180 0` for private logs and PPM capture |
| Menus rendered | NOT YET VERIFIED | Native frame dump then browser check |
| Match in-game | NOT YET VERIFIED | Select teams, start match, render players/ball |
| Keyboard/gamepad/mobile touch | NOT YET VERIFIED | End-to-end browser hardware tests |
| Unraid deployment | CONFIG ONLY | `scripts/unraid-build.sh`, `compose.yaml`, `deploy/nginx.conf`; not tested on Unraid |

## Focused debugging loop

1. Build with `--native` and keep `work/logs/port-*.log` (passed on AEROCOOL).
2. Run `PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 0` for private boot traces and capture.
3. Compare first exception / unsupported HLE or missing guest function against runtime implementation.
4. Inspect first exact failure: `No recompiled function registered`, unimplemented HLE, filesystem failure, or GE draw failure.
5. Add reproducible tests or trace assertions *before* changes to upstream runtime.
6. Apply minimal game-specific changes as patches under this project (future milestone), rather than copying proprietary generated code into Git.
7. Iterate to a stable menu, then to a complete match. Record actual tested browser/hardware FPS, not estimates.

The previously reported guest address `0x089864D0` is a **lead** from an earlier experiment, not a diagnosis. The exact plain ELF and backtrace are needed to identify the missing dispatch entry.
