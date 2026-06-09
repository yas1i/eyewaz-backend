# EYEWAZ Urdu — Windows SAPI5 voice (JAWS, Narrator, every app)

A **SAPI5** voice is the universal way to add a voice to Windows: once installed,
**JAWS, Narrator, Windows Magnifier, Word's Read Aloud, and any SAPI app** can
speak Urdu with it. This is the path NVDA *doesn't* cover (JAWS has no add-on
speech API).

This folder is a **working scaffold** — the COM plumbing, the SAPI interfaces,
the HTTP-to-Piper synthesis, and the voice-token registration are all here. It
needs a **Windows build** (MSVC + Windows SDK) and one round of on-device
fleshing-out (mainly word-boundary events). It is intentionally thin: the actual
voice is your trained Piper model served locally by `../tts-local`.

## Architecture
```
JAWS / Narrator / any app
        │  (SAPI5)
        ▼
  EyewazTts.dll   ── HTTP POST /tts ──►  tts-local/piper_server.py  ──►  your Piper .onnx
 (this project)                          (127.0.0.1:59125, offline)
```
Keeping synthesis in the local Python server means the same trained voice powers
NVDA, Chrome, Android, *and* JAWS — one model, every surface — and the DLL stays
small.

## Files
| File | Role |
|---|---|
| `src/guids.h` | The voice's CLSID (**replace with your own `uuidgen`**) + token id |
| `src/EyewazTtsEngine.{h,cpp}` | `ISpTTSEngine::Speak`/`GetOutputFormat` + `ISpObjectWithToken`; WinHTTP POST to the local server, WAV decode, rate/volume, abort handling |
| `src/dll.cpp` | COM class factory + `DllRegisterServer` (creates the SAPI voice token) |
| `src/EyewazTts.def` | DLL exports |
| `CMakeLists.txt` | MSVC build |
| `register/install.ps1` | `regsvr32` install / uninstall |

## Build & install
```powershell
# 1) Build (Developer PowerShell for VS, Windows SDK installed)
cmake -S . -B build -A x64
cmake --build build --config Release

# 2) Start the local voice (in another window)
python ..\tts-local\piper_server.py --model C:\path\eyewaz-urdu-female.onnx

# 3) Register the voice (ELEVATED)
.\register\install.ps1
```
Then choose **EYEWAZ Urdu** in JAWS → Options → Voices, or Narrator settings, or
Control Panel → Speech.

## Before shipping
- **Generate a unique CLSID** (`uuidgen`) and paste it into `src/guids.h`. Never
  ship the placeholder GUID.
- **Build both x64 and Win32** so 32- and 64-bit screen readers can load it.
- **Code-sign** the DLL + ship a signed MSI (the `install.ps1` logic moves into
  the installer; bundle the local server + model so users do nothing).
- **Auto-start the local server** (Task Scheduler "At log on", or inside the MSI)
  so the voice is always available.

## What's stubbed (the fleshing-out)
- **Word-boundary events** (`SPEI_WORD_BOUNDARY`) for caret/word tracking —
  marked `// TODO` in `Speak()`. Reading works without it; precise highlighting
  needs mapping character offsets to sample offsets and calling `pSite->AddEvents`.
- **Male voice / voice picker** — register a second token (Gender=Male) pointing
  at a second local-server port, or add a `?voice=` switch.
- Verify the exact `sapi.lib` path on your SDK if CMake can't auto-find it.

## Why not embed Piper in C++?
We could (via onnxruntime + a C++ phonemizer), and that removes the local server
dependency — a good v2. For now, reusing the Python server is far less code and
guarantees identical audio to every other EYEWAZ surface.
