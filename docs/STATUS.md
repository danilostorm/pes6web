# PES6Web build / bring-up status

Last evaluated: 2026-10-11 on AEROCOOL via Desktop Commander. Native PSP recompilation is confirmed, and the runtime now completes one host frame. Its framebuffer capture is entirely black and it immediately halts; no visible or playable PES6 runtime has been demonstrated.

| Gate | Status | Evidence / next step |
| --- | --- | --- |
| Confirm game files | DONE | EU ISO, extracted PSP_GAME assets available in user's Drive (not committed) |
| Identify executable | DONE | `EBOOT.BIN` is a `~PSP` encrypted module; `BOOT.BIN` is zero-filled |
| Inspector + unit tests | DONE | `tools/inspect_psp.py`, standard-library test suite |
| Recomp toolchain wrapper | CREATED / UNTESTED ON GAME | `scripts/bootstrap.sh`, `scripts/port.sh` wrap upstream toolchain |
| Decrypt retail executable | DONE | AEROCOOL log: tag `C0CB167C` decrypted to a 1,914,920-byte ELF |
| Generate C++ from actual PES6 ELF | DONE | 6,757 seeds; 343,280 emitted PCs; 87,727 registered blocks; 117 units |
| Compile native / Wasm | DONE | Native and browser builds linked successfully on AEROCOOL; no gameplay confirmed |
| Native boot | ACTIVE DEBUGGING | HLE module lookup fixed; first halt `0x0897FD08` cleared. Subsequent indirect-entry gaps `0x08986598`, `0x089864DC`, `0x089864D0`, `0x08984284` cleared. First native host frame reached after further indirect-entry recovery. Last validated halt: `0x088BE928`, 1 frame. A BEQ-zero post-delay-slot CFG fix is currently rebuilding on AEROCOOL. |
| Menus rendered | NOT YET VERIFIED | Native frame dump then browser check |
| Match in-game | NOT YET VERIFIED | Select teams, start match, render players/ball |
| Keyboard/gamepad/mobile touch | NOT YET VERIFIED | End-to-end browser hardware tests |
| Unraid deployment | CONFIG ONLY | `scripts/unraid-build.sh`, `compose.yaml`, `deploy/nginx.conf`; not tested on Unraid |

## Current first-boot investigation

- First native test: `we10psp` loaded with 229 imports; 87746 registered entries; unsupported Allegrex `0x00000000` at `0x0897FD08`, `user_main` return address `0x0897E524`, zero frames, framebuffer 0.
- Unimplemented NID `ModuleMgrForUser::0xD8B73127` is `sceKernelGetModuleIdByAddress`. Returned zero from fallback; now a source-only pinned-upstream HLE patch associates the reserved module range with an UID and returns `0x8002012E` for unknown ranges.
- CI checks the source-only patches' idempotency; 20 source unit tests also passed directly on AEROCOOL. **Passing CI does not mean PES6 boots.** The module lookup fallback no longer appears in the native log.
- A source-only, opt-in `PSPRECOMP_EXTRA_SEEDS` patch recovers indirect jump landing addresses without uploading retail game code. The private verified seed file at `work/diagnostics/verified-extra-seeds.txt` is reused by `scripts/port.sh`; 338 candidate entries from the startup region are in the current private seed file and passed an incremental native build. AEROCOOL reached 1 host frame; framebuffer `0x04044000`, all-black captured PPM. After recovering `0x088C4330` (post-JR), the guest reached additional semaphores/threads but stopped at `0x088BE928`, after the unconditional `BEQ $zero,$zero` at `0x088BE920`. The bounded CFG patch now recognizes this branch pattern, and a new native + Wasm build is in progress.
- The invalid function entry may be a separate recompilation/control-flow bug. Do not mask it by forcing the PC forward or fabricating a successful run.

- Additional runtime HLE calls observed: InterruptManager `0xCA04A2B9`, `0xFB8E22EC`; `sceUmdRegisterUMDCallBack`, `sceUmdUser::0x4A9E5E29`, `sceIoDevctl`; `sceUtility::0x0D5BC6D2`, `0x1579A159`, `0xC629AF26`. The new `ThreadManForUser::0x6652B8CA` was identified as `sceKernelSetAlarm`; the others were identified from PSP SDK / PPSSPP source. Never treat returning zero by fallback as a correct implementation.
- Private native diagnostic: `work/diagnostics/native-20261011-212932-1297096/run.log`. Image `frame.ppm` is pure black (all 130,560 RGB pixels zero).

## Focused debugging loop

1. Build with `--native` and keep `work/logs/port-*.log` (passed on AEROCOOL).
2. Run `PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 0` for private boot traces and capture.
3. Compare first exception / unsupported HLE or missing guest function against runtime implementation.
4. Inspect first exact failure: `No recompiled function registered`, unimplemented HLE, filesystem failure, or GE draw failure.
5. Add reproducible tests or trace assertions *before* changes to upstream runtime.
6. Apply minimal game-specific changes as patches under this project (future milestone), rather than copying proprietary generated code into Git.
7. Iterate to a stable menu, then to a complete match. Record actual tested browser/hardware FPS, not estimates.

Previously resolved guest addresses include `0x0897FD08`, `0x089864D0`, `0x088C4330` through targeted ELF-backed CFG discovery. Runtime boot and game rendering remain unverified.
