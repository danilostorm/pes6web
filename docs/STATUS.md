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

### Remote Agent Recovery and GE sync trace (2026-10-12)

- Remote Desktop Commander supervisor installed on AEROCOOL as PID 1889161, PPID 1, independently of SSH, via `scripts/install-remote-commander-unraid.sh`. Reboot persistence configured but not yet reboot-tested.
- The source-only `PES6_TRACE_GE_EVENTS=1` diagnostic was compiled and run natively: **300 frames completed, framebuffer all black**. PSP GE lists execute `FINISH` followed by `END`; **no SIGNAL command was observed**. The first 18 GE draw primitives were `type=6` sprites with `clear=1`.
- The guest calls `sceGeSetCallback` once with a non-null guest callback-data pointer, but current runtime registers this NID to a return-zero stub. HLE trace recorded 447 `sceGeListEnQueue` calls, 151 `sceGeDrawSync` calls and 150 vblank waits over 150 guest frames; graphics processing and vblank progress, but scene geometry never appears.
- Next: inspect the four words of the guest `SceGeCallbackData` structure (signal handler/arg and finish handler/arg), and implement/deliver callback only if handlers are valid and guest uses the event. The GE trace alone does **not** establish missing FINISH callback delivery as the root cause of black screen.
- The game image, extracted data and runtime test log remain private on AEROCOOL. No playable release or browser-gameplay validation.

### 2026-10-12 direct development: ISO LBN + experimental GE FINISH

- The Unraid daily PES6Web cron and its reboot registration were removed at user request; the unrelated Remote Desktop Commander supervisor stays online. The hourly ChatGPT automation was disabled. Source-only work now proceeds on demand.
- Added native, opt-in ISO-backed window support for PSP raw-sector pseudo-paths such as disc0:/sce_lbn0x10_size0x4000. With no PES6_DISC_ISO supplied, the existing file behavior remains. Its source patch is idempotent and scoped specifically to the two seek handlers. 62 Python tests, synthetic pathname parser tests, C++ syntax compilation and GitHub CI succeeded. This does NOT imply runtime gameplay success; browser ISO sector support is not yet implemented.
- Added an **experimental, disabled-by-default** GE FINISH event bridge (PES6_ENABLE_GE_FINISH_CALLBACKS=1). The graphics worker records FINISH command tokens in a bounded, mutex-protected queue; guest callbacks are scheduled on CPU threads and their stacks reclaimed on normal return. SceGeSetCallback and SceGeUnsetCallback now track the callback slots.
- Native build and link succeeded after rebuilding 10 changed host units. 64 Python tests passed. Native A/B runs (240 frames each, callbacks off vs on) both exited normally but remained ALL BLACK (0/130560 visible pixels). An additional 180-frame opt-in run with PES6_TRACE_GE_FINISH_DISPATCH=1 confirmed the kernel scheduled callback id 0 at guest function address, but pixels stayed ALL BLACK. **Scheduling was observed; this does not prove every callback executed or that PSP interrupt semantics are fully emulated**. GE SIGNAL events still require separate handling.
- No game executable, ISO, copyrighted resources or private test logs were committed. Do not publish a playable release until actual menu, controls and gameplay are verified.

### 2026-10-12 raw ISO asynchronous timing experiment

- Compared identical native binaries with a private, read-only mounted ISO; used PES6_DISC_ISO to enable raw logical sector reads. With no ISO variable, raw-sector support remains inactive.
- Immediate read: sceIoOpen(disc0:/sce_lbn0x10_size0x4000) and sceIoReadAsync of 0x4000 succeeded, then guest invalid memory access at 0x6E3ED9A7, guest PC 0x0887A1A8. Native run reported 2 frames, all-black image.
- Deferred read: disabled-by-default PES6_RAW_ASYNC_DEFER=1 delays raw-sector completion until next frame I/O poll. Trace confirms read-raw-queued, 16384 bytes read, read-raw-complete and asynchronous result delivery. The SAME invalid address and PC occurred after 4 frames, again all-black.
- This A/B result rules out the tested one-frame delay alone as a fix. It does not establish whether the cause is guest parsing, recompiler arithmetic, or another missing PSP service. No claim of playable PES6 is justified.
- Reference PPSSPP accepts raw disc paths as bounded ISO sectors and consumes async poll results. Unlike PPSSPP, the host does not fully model the one-shot sceIoPollAsync result lifecycle. This is an additional, independently testable compatibility gap, not proven as crash cause.
- Private A/B logs: /mnt/cache/pes6web-native-trace/raw-async-instant.log and raw-async-deferred.log. No ISO, protected executable, generated guest code, or private logs are committed.
- 66 source tests passed locally, native host changes recompiled, experimental native executable linked and A/B native runs completed. Browser was not rebuilt or tested.

### 2026-10-12 memory fault narrowing and combined tests

- Four actual native configurations were compared against the user's read-only ISO: raw I/O immediate with GE callback dispatch disabled/enabled, and raw I/O delayed by one frame with GE dispatch disabled/enabled. All four reached **the same guest invalid RAM address 0x6E3ED9A7 at guest PC 0x0887A1A8**: immediate tests after 2 frames; delayed tests after 4 frames; all yielded **0/130560 visible pixels**. Host native process exit code 0 only means the diagnostic runner exited; the guest was **halted**, not playable.
- The sector read itself returned all 16384 requested bytes. A standalone source-only C++ harness, generated from the project's existing RAW_HELPER and RAW_READ implementation and fed by a synthetic ISO image, verified a 16384-byte sector window, checked every output byte, guard/sentinel bytes around destination, virtual EOF, relative seek, rejection of an invalid guest destination and an out-of-range LBA. No proprietary game code was compiled into this test.
- The open-source psprecomp::GuestMemory unaligned LWL/LWR operations passed 84 synthetic comparisons (28 addresses, both load merge orders and an uncached alias) using the existing native core library. This verifies only that memory helper, **not** all recompiled CPU instructions or the game's call path.
- A direct four-byte little-endian search in the ISO9660 sector window found **no literal occurrence of 0x6E3ED9A7**. This does not identify where the pointer came from: it may be calculated or originate elsewhere. Register dumps may also contain stale cached registers on unwinding.
- The baseline (with missing raw-sector open) repetitively called sceIoPollAsync on an invalid descriptor 0x80010002. Providing that device access removes the repeated failed operation but exposes the same deterministically reproducible memory fault. PSP async result lifecycle still merits a separate compatibility test; one-shot behavior is documented by PPSSPP but is not proven to cause this specific crash.
- **Next priority:** narrow the provenance of the pointer used by the faulting guest instruction using authorized diagnostic metadata, and check the AOT memory/load/branch semantics without forcing the PC forward or fabricating success. Do not enable the GE FINISH or raw I/O timing experiments by default. WebAssembly and gameplay are not yet verified.

## Focused debugging loop

1. Build with `--native` and keep `work/logs/port-*.log` (passed on AEROCOOL).
2. Run `PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 0` for private boot traces and capture.
3. Compare first exception / unsupported HLE or missing guest function against runtime implementation.
4. Inspect first exact failure: `No recompiled function registered`, unimplemented HLE, filesystem failure, or GE draw failure.
5. Add reproducible tests or trace assertions *before* changes to upstream runtime.
6. Apply minimal game-specific changes as patches under this project (future milestone), rather than copying proprietary generated code into Git.
7. Iterate to a stable menu, then to a complete match. Record actual tested browser/hardware FPS, not estimates.

Previously resolved guest addresses include `0x0897FD08`, `0x089864D0`, `0x088C4330` through targeted ELF-backed CFG discovery. Runtime boot and game rendering remain unverified.
