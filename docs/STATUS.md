# PES6Web build / bring-up status

Last evaluated: 2026-10-11. Native initial run completed with 0 frames (guest halted); no playable runtime has been demonstrated. An HLE patch is pending verification on AEROCOOL.

| Gate | Status | Evidence / next step |
| --- | --- | --- |
| Confirm game files | DONE | EU ISO, extracted PSP_GAME assets available in user's Drive (not committed) |
| Identify executable | DONE | `EBOOT.BIN` is a `~PSP` encrypted module; `BOOT.BIN` is zero-filled |
| Inspector + unit tests | DONE | `tools/inspect_psp.py`, standard-library test suite |
| Recomp toolchain wrapper | CREATED / UNTESTED ON GAME | `scripts/bootstrap.sh`, `scripts/port.sh` wrap upstream toolchain |
| Decrypt retail executable | DONE | AEROCOOL log: tag `C0CB167C` decrypted to a 1,914,920-byte ELF |
| Generate C++ from actual PES6 ELF | DONE | 6,757 seeds; 343,280 emitted PCs; 87,727 registered blocks; 117 units |
| Compile native / Wasm | DONE | Native and browser builds linked successfully on AEROCOOL; no gameplay confirmed |
| Native boot | FAILED (first run) | 0 frames; unimplemented `sceKernelGetModuleIdByAddress` (NID `0xD8B73127`); guest halt at `0x0897FD08` |
| Menus rendered | NOT YET VERIFIED | Native frame dump then browser check |
| Match in-game | NOT YET VERIFIED | Select teams, start match, render players/ball |
| Keyboard/gamepad/mobile touch | NOT YET VERIFIED | End-to-end browser hardware tests |
| Unraid deployment | CONFIG ONLY | `scripts/unraid-build.sh`, `compose.yaml`, `deploy/nginx.conf`; not tested on Unraid |

## Current first-boot investigation

- First native test: `we10psp` loaded with 229 imports; 87746 registered entries; unsupported Allegrex `0x00000000` at `0x0897FD08`, `user_main` return address `0x0897E524`, zero frames, framebuffer 0.
- Unimplemented NID `ModuleMgrForUser::0xD8B73127` is `sceKernelGetModuleIdByAddress`. Returned zero from fallback; now a source-only pinned-upstream HLE patch associates the reserved module range with an UID and returns `0x8002012E` for unknown ranges.
- CI checks the source-only patch's idempotency and missing-anchor behavior. **CI success does not validate that the PES6 boot issue is fixed.** Rebuild native+Wasm on AEROCOOL, rerun smoke test and inspect next stop.
- The invalid function entry may be a separate recompilation/control-flow bug. Do not mask it by forcing the PC forward or fabricating a successful run.

## Focused debugging loop

1. Build with `--native` and keep `work/logs/port-*.log` (passed on AEROCOOL).
2. Run `PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 0` for private boot traces and capture.
3. Compare first exception / unsupported HLE or missing guest function against runtime implementation.
4. Inspect first exact failure: `No recompiled function registered`, unimplemented HLE, filesystem failure, or GE draw failure.
5. Add reproducible tests or trace assertions *before* changes to upstream runtime.
6. Apply minimal game-specific changes as patches under this project (future milestone), rather than copying proprietary generated code into Git.
7. Iterate to a stable menu, then to a complete match. Record actual tested browser/hardware FPS, not estimates.

The previously reported guest address `0x089864D0` is a **lead** from an earlier experiment, not a diagnosis. The exact plain ELF and backtrace are needed to identify the missing dispatch entry.
