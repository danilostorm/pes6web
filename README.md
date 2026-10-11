# PES6Web — PSP static recompilation experiment

**Status: infrastructure/diagnostics only. Not a playable port.** The objective is to run PES 6 PSP directly in a browser with WebAssembly and WebGL2, *not* streaming video from an emulator. The initial integration uses [snuri00/psp-web-recomp](https://github.com/snuri00/psp-web-recomp), pinned to `95d088239cfb09c22fe4ee9d98671ede371f2a4b` for reproducibility. Upstream has demonstrated other PSP games, **not PES 6**. PES 6 will require per-game runtime/HLE/graphics work.

No retail game binaries, generated recompilation code, game assets or ROMs belong in this public repository. Provide your own lawful dump locally. Do not upload generated Wasm or decrypted executable to public hosting without distribution rights.

## Requisitos

Linux (Ubuntu/Unraid VM preferred), git, Python 3.10+, CMake, Ninja, Clang or GCC with C++20, Make, OpenSSL/zlib development libraries. About 2+ GB free for one game; additional free space for emsdk and toolchain. For native testing: `libegl-dev`, `libgles-dev`. Building the game needs a local decrypted PSP ELF, or `pspdecrypt` to decrypt its retail EBOOT. Docker is only needed for optional web serving.

On Debian / Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 cmake ninja-build clang make libssl-dev zlib1g-dev libegl-dev libgles-dev
```

## Quick start (local, no protected game data in Git)

```bash
git clone https://github.com/danilostorm/pes6web.git
cd pes6web
make test
# Input can be the original ISO, or the parent folder that contains PSP_GAME/:
make inspect DISC="/path/to/extracted/PES6"
bash scripts/bootstrap.sh           # clones PSP Web Recomp and prepares SDK
bash scripts/build-decrypter.sh    # separate GPLv3 pspdecrypt utility; local only
bash scripts/port.sh "/path/to/Pro Evolution Soccer 6.iso" --native
bash scripts/serve.sh              # http://localhost:8613/
```

`--native` optionally builds the headless diagnostic runner. If the executable has been independently decrypted from your own dump, you can pass `PES6_DECRYPTED_ELF=/path/to/plain.elf` to `scripts/port.sh` and skip `build-decrypter.sh`.

**What a successful build means:** the generated code linked successfully. It does **not** mean that PES 6 boots, renders, or plays. Capture `work/logs/port-*.log` and any runtime errors. Fix missing system calls, incorrect GE behavior, guest dispatch, and filesystem accesses before claiming success.

## Important findings for the EU PSP dump

- `PSP_GAME/SYSDIR/EBOOT.BIN` starts with `~PSP`: encrypted executable.
- `PSP_GAME/SYSDIR/BOOT.BIN` is all zero bytes: it cannot be used as the decrypted executable.
- `PARAM.SFO` metadata can be parsed with the included inspector.
- Other `USRDIR` assets are needed at runtime and served privately through HTTP Range, not checked into Git.

See [docs/STATUS.md](docs/STATUS.md) for measurable milestones.

## First runtime smoke test (AEROCOOL, no recompilation)

The real PSP executable now decrypts and compiles, but has not been confirmed to boot or draw PES6. After building with `--native`, use:
```bash
cd /mnt/user/appdata/pes6web
git pull --ff-only
PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 0
# Later: optional headless OpenGL test (may need Mesa software rendering)
# PES6_NATIVE_TIMEOUT=180 PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh 180 1
```
The script runs without network and writes a private `run.log` and (if the guest draws) `frame.ppm` under `.../pes6web-work/diagnostics/native-*`. A zero exit code only reports that the native runner exited; it does not prove gameplay. Check the **first** runtime failure and actual rendered pixels.
To send a diagnostic without proprietary files:
```bash
tail -n 100 "$(ls -1t /mnt/user/Downloads/pes6web-work/diagnostics/native-*/run.log | head -n 1)"
```

## Serve a **working local build** from Unraid / Docker

After `scripts/port.sh` creates `dist/index.html` and `work/psp-web-recomp/games/pes6/root/disc/`:

```bash
PES6_PORT=8613 docker compose up -d
```

The Nginx config emits COOP/COEP headers required by SharedArrayBuffer and exposes `/disc/` for byte-range asset reads. For initial debugging, use `scripts/serve.sh` first; it uses upstream's own server. Reverse proxies must preserve headers and Range semantics. **Exposing the result publicly may redistribute copyrighted data — use private access only unless you have rights.**


### Unraid: compilação em Docker sem ocupar o armazenamento de imagens

Deixe a ISO original em uma pasta local do Unraid, por exemplo `/mnt/user/Downloads/PES6.iso`. Depois execute:

```bash
cd /mnt/user/appdata
git clone https://github.com/danilostorm/pes6web.git
cd pes6web
PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/unraid-build.sh /mnt/user/Downloads/PES6.iso --native
```

O container-builder monta os arquivos e guarda SDK, disco extraído, ferramentas, logs e código gerado em `/mnt/user/Downloads/pes6web-work` (fora da imagem do Docker). O processo usa bastante CPU/RAM, vários GB e acesso à internet. O resultado de um build não significa que a partida funcione. **Não rode a compilação enquanto houver pouco espaço livre.**

Para hospedar um build *após* existir `dist/index.html`:

```bash
PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work PES6_PORT=8613 docker compose up -d
```

Se a ISO estiver em outro caminho, altere somente o argumento do arquivo. Arquivos do jogo continuam fora do GitHub.

## Testing

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/*.sh
```

The CI does not compile PES 6 or download the game. It tests just our open-source diagnostics and wrappers.

## Technical credits

- [PSP Web Recomp](https://github.com/snuri00/psp-web-recomp) (MIT; downloaded as a separate checkout)
- [PSPRecomp](https://github.com/jessicanataliagta/PSPRecomp) (installed upstream)
- [pspdecrypt](https://github.com/John-K/pspdecrypt) (GPLv3; separate external CLI process, not embedded)

PES and PlayStation are trademarks of their respective owners. This is an unaffiliated research experiment.
