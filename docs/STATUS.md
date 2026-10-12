# PES6Web build / bring-up status

Last evaluated: 2026-10-11 on AEROCOOL via Desktop Commander. Native PSP recompilation is confirmed, and the runtime now completes one host frame. Its framebuffer capture is entirely black and it immediately halts; no visible or playable PES6 runtime has been demonstrated.

| Gate | Status | Evidence / next step |
| --- | --- | --- |
| Confirm game files | DONE | EU ISO, extracted PSP_GAME assets available in user's Drive (not committed) |
| Identify executable | DONE | `EBOOT.BIN` is a `~PSP` encrypted module; `BOOT.BIN` is zero-filled |
| Inspector + unit tests | DONE | `tools/inspect_psp.py`, standard-library test suite |
| Recomp toolchain wrapper | TESTED ON GAME | `scripts/bootstrap.sh`, `scripts/port.sh`, `scripts/unraid-build.sh` validated on AEROCOOL |
| Decrypt retail executable | DONE | AEROCOOL log: tag `C0CB167C` decrypted to a 1,914,920-byte ELF |
| Generate C++ from actual PES6 ELF | DONE | 6,757 seeds; 343,280 emitted PCs; 87,727 registered blocks; 117 units |
| Compile native / Wasm | DONE | Native and browser builds linked successfully on AEROCOOL; no gameplay confirmed |
| Native boot | ACTIVE DEBUGGING | HLE module lookup fixed; first halt `0x0897FD08` cleared. Subsequent indirect-entry gaps `0x08986598`, `0x089864DC`, `0x089864D0`, `0x08984284` cleared. First native host frame reached after further indirect-entry recovery. Last verified halt: `0x08886DC8` after recovering `0x0886A7E8`, still 1 black frame. A bounded expansion covering `0x08880000-0x08890000` is being compiled; no menu is rendered. |
| Menus rendered | NOT YET VERIFIED | Native frame dump then browser check |
| Match in-game | NOT YET VERIFIED | Select teams, start match, render players/ball |
| Keyboard/gamepad/mobile touch | NOT YET VERIFIED | End-to-end browser hardware tests |
| Unraid deployment | CONFIG ONLY | `scripts/unraid-build.sh`, `compose.yaml`, `deploy/nginx.conf`; not tested on Unraid |

## Current first-boot investigation

- First native test: `we10psp` loaded with 229 imports; 87746 registered entries; unsupported Allegrex `0x00000000` at `0x0897FD08`, `user_main` return address `0x0897E524`, zero frames, framebuffer 0.
- Unimplemented NID `ModuleMgrForUser::0xD8B73127` is `sceKernelGetModuleIdByAddress`. Returned zero from fallback; now a source-only pinned-upstream HLE patch associates the reserved module range with an UID and returns `0x8002012E` for unknown ranges.
- CI checks the source-only patches' idempotency; 40 source unit tests passed directly on AEROCOOL (including private ELF validation, bounded boot recovery and UMD HLE patch checks). **Passing CI does not mean PES6 boots.** The module lookup fallback no longer appears in the native log.
- A source-only, opt-in `PSPRECOMP_EXTRA_SEEDS` patch recovers indirect jump landing addresses without uploading retail game code. The private verified seed file at `work/diagnostics/verified-extra-seeds.txt` is reused by `scripts/port.sh`; 344 verified private seed entries are retained in the private file and passed an incremental native build. AEROCOOL reached 1 host frame; framebuffer `0x04044000`, all-black captured PPM. After recovering `0x088C4330` (post-JR), the guest reached additional semaphores/threads but stopped at `0x088BE928`, after the unconditional `BEQ $zero,$zero` at `0x088BE920`. The bounded CFG patch now recognizes this branch pattern, ; native + Wasm were built, then additional native-only recovery iterations were performed. These later native improvements have not yet been ported into the web build.
- The invalid function entry may be a separate recompilation/control-flow bug. Do not mask it by forcing the PC forward or fabricating a successful run.

- Additional runtime HLE calls observed: InterruptManager `0xCA04A2B9`, `0xFB8E22EC`; `sceUmdRegisterUMDCallBack`, `sceUmdUser::0x4A9E5E29`, `sceIoDevctl`; `sceUtility::0x0D5BC6D2`, `0x1579A159`, `0xC629AF26`. The new `ThreadManForUser::0x6652B8CA` was identified as `sceKernelSetAlarm`; the others were identified from PSP SDK / PPSSPP source. Never treat returning zero by fallback as a correct implementation.
- Private native diagnostic: `work/diagnostics/native-20261011-212932-1297096/run.log`. Image `frame.ppm` is pure black (all 130,560 RGB pixels zero).

## Evidence-based graphics gate (2026-10-11)

- Native OpenGL ES initialized on AEROCOOL using Mesa llvmpipe (software rendering). A driver-context initialization issue is **not** the immediate blocker.
- Native image is **all black (0/130,560 nonblack pixels)** both with GL disabled and GL enabled.
- After initial jump recovery and HLE fixes: GE lists=3, GE primitives=1, GE sprites=1, GE triangle count=0, GE pixels=0, native GL draw calls=0, GL uploads=0, and 1 host frame completed.
- Guest halted on `0x08886DC8` with a missing compiled entry. Source-generation now includes that address; next bound must be validated with an actual native run.
- The diagnostic instrumentation reports GPU counters even when boot halts before 60 frames. `tools/check_ppm.py` tests whether any RGB pixels changed; a nonblack frame alone does **not** prove a menu or gameplay.
- Until a native run produces multiple frames *and* a nonblack image, do not label a package as playable or publish a release.

## Latest conclusive AEROCOOL result (2026-10-11 23:59 Brazil)

- `PSPRecomp` native build successfully completed (87/87 steps) after recovering `0x0897FEB4`: 10,482 function seeds, 352,118 emitted PCs and 90,866 registered blocks.
- Latest native OpenGL smoke: **1,800/1,800 frames completed, 59.94 Hz emulated PSP timebase, but 0/130,560 nonblack framebuffer pixels**. The GL backend executes approximately one draw call per frame, 60 primitives and 480 sprites per 60-frame interval; the capture stays black.
- Latest local private trace: `/mnt/user/Downloads/pes6web-work/diagnostics/native-20261011-235905-1742534/run.log`. No native build remains active.
- Confirmed unimplemented syscall: `UtilsForUser::sceKernelSetGPO` (debug LED GPIO). The previous sema status NID is now handled, but restoring correct semaphore semantics by itself did **not** produce visible graphics.
- A prior test with sema-status fix and before additional CFG recovery halted after 2 frames at `0x0897FEB4`; that address is now compiled and the guest again runs 1,800 frames. Not playable, no menu observed.
- Browser build is **stale relative to native-only recovery**; no functional browser PES6 launch has been verified. Do not ship a release or imply 1,800 frames means gameplay is working.
- Next investigation should trace **state progression and asset loads** (open/read operations and transition into GUI initialization) and inspect GE sprite textures / draw output; expanding MIPS seeds alone is no longer sufficient to explain the black display.

## 2026-10-12: native black-screen investigation (verified on AEROCOOL)

- The native PES6 launcher builds and runs for **1,800 guest frames** without a guest halt, but the captured 480x272 framebuffer contains **0/130,560 nonblack pixels**, consistently from frame 120 through frame 1800.
- **Actual async game file reads succeed** from the extracted ISO: `disc0:/PSP_GAME/USRDIR/0_sound.afs` (6,144 bytes), `0_text.afs` (96,256 bytes), `e_text.afs` (4,096 bytes), and `over.afs` (2,048 bytes). Initial file-access failure is *not* the explanation for the blank display.
- The virtual controller is polled (about 298 reads per 300 guest frames). Pressing **Start** and **Cross** over a 600-frame test did not produce any nonblack pixels or change the 1-primitive/8-sprite-per-frame drawing pattern.
- UMD activation now queues the READY/PRESENT/READABLE callback and `sceKernelCheckCallback` delivers the guest function via `call_guest`; a private 600-frame test confirmed delivery. This HLE correctness fix **did not** make a visible frame.
- **GE primitive tracing shows only screen-clear draws:** the first 18 primitives were PSP sprite primitive type 6 with `clear=1`. After startup, the guest repeatedly submits 1 primitive / 8 sprites per frame; the graphics backend can render GL calls but the game is not yet submitting menu or gameplay geometry.
- HLE profiling over 300 frames shows repeated activity (including `sceCtrlReadBufferPositive`, `sceDisplayWaitVblankStart`, `sceGeListEnQueue`, audio and semaphore operations), not a generic guest crash. The scene initialization/progress and potential missing firmware event behavior are the next debugging target.
- Reproducible source-only instrumentation: `tools/patch_psp_private_diagnostics.py` (opt-in `PES6_TRACE_IO=1`, `PES6_TRACE_GE=1`) and `tools/patch_psp_umd_callback_dispatch.py`. Local suite: **52 tests passed**. Logs, captures and commercial ISO assets remain private on AEROCOOL.
- The **browser WebAssembly build has not been validated as playable** and is behind the native-only changes. Do not publish a PES6Web gameplay release or infer that completing 1,800 frames means gameplay is functional.

### Next validation: GE command callbacks and synchronization

- The GE HLE currently registers `sceGeSetCallback` as a return-zero stub. The upstream GE interpreter handles list FINISH as a register update, but does not yet deliver PSP SIGNAL/FINISH interrupts to the game's registered callback; **this is a suspected compatibility gap, not a proven black-screen root cause**.
- New opt-in instrumentation `tools/patch_psp_ge_event_trace.py` prints bounded GE list starts and SIGNAL/FINISH/END commands without changing emulation behavior. `scripts/smoke-native.sh` now forwards `PES6_TRACE_GE_EVENTS=1` into the isolated Docker runner and rejects a zero-length/non-executable binary.
- On AEROCOOL **after reconnecting and rebuilding the native host**: `PES6_TRACE_GE_EVENTS=1 PES6_TRACE_GE=1 PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 1`. Compare `[ge-event]` and `[ge-prim]` logs with the existing GE clear-only baseline. These new GE event traces have not yet been run on the game ISO.
- Source/static GitHub CI passed for new instrumentation; actual game rendering remains unverified. All ISO, generated proprietary code, and private traces must stay off the public repository.

## Focused debugging loop

1. Build with `--native` and keep `work/logs/port-*.log` (passed on AEROCOOL).
2. Run `PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 0` for private boot traces and capture.
3. Compare first exception / unsupported HLE or missing guest function against runtime implementation.
4. Inspect first exact failure: `No recompiled function registered`, unimplemented HLE, filesystem failure, or GE draw failure.
5. Add reproducible tests or trace assertions *before* changes to upstream runtime.
6. Apply minimal game-specific changes as patches under this project (future milestone), rather than copying proprietary generated code into Git.
7. Iterate to a stable menu, then to a complete match. Record actual tested browser/hardware FPS, not estimates.

Previously resolved guest addresses include `0x0897FD08`, `0x089864D0`, `0x088C4330` through targeted ELF-backed CFG discovery. Runtime boot and game rendering remain unverified.
