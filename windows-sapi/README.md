# EYEWAZ Urdu — Windows SAPI5 voice (JAWS, Narrator, every app)

A **SAPI5** voice is the universal way to add a voice to Windows: once installed,
**JAWS, Narrator, Windows Magnifier, Word's Read Aloud, and any SAPI app** can
speak Urdu with it. This is the path NVDA *doesn't* cover (JAWS has no add-on
speech API).

**Built, registered and verified end-to-end (14 Aug 2026)** in a Windows 11 ARM
VM: `regsvr32` succeeds, the voice enumerates in SAPI (`System.Speech` lists
"EYEWAZ Urdu" alongside the Microsoft voices), and `SpeechSynthesizer.Speak`
produces real Urdu audio through this DLL -> local piper server -> piper.exe.
Only word-boundary events remain stubbed (see below). It is intentionally thin:
the actual voice is your trained Piper model served locally by `../tts-local`.

Two fixes were needed to make the scaffold actually run:
- **No ATL.** The engine now uses `Microsoft::WRL::ComPtr` (Windows SDK), not
  ATL's `CComPtr`, so the build needs only the "Desktop development with C++"
  workload, no ATL component, and the DLL carries no ATL redistributable.
- **No `__declspec(novtable)`.** The class is instantiated directly
  (`new CEyewazTtsEngine`), so the original `ATL_NO_VTABLE` suppressed vtable
  setup and SAPI's first virtual call crashed (AccessViolation). Removed.

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
```bat
REM 1) Build BOTH arches in one shot (finds MSVC via vswhere). Tested path.
build.bat
REM    -> src\EyewazTts-arm64.dll and src\EyewazTts-x64.dll
REM    (CMakeLists.txt still works too: cmake -S . -B build -A x64)

REM 2) Start the local voice (another window). On Windows-on-ARM, or any box
REM    without piper1-gpl's espeakbridge, shell out to the bundled piper.exe:
python ..\tts-local\piper_server.py ^
  --piper-exe C:\path\to\piper.exe ^
  --model C:\path\to\eyewaz-urdu-female.onnx --port 59125

REM 3) Register the voice (ELEVATED) — pick the arch that matches the host/host app
regsvr32 src\EyewazTts-x64.dll
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

## Word-boundary events (done)
`Speak()` now reports `SPEI_WORD_BOUNDARY` so JAWS/Narrator can follow and
highlight the spoken word (surfaces as `SpeechSynthesizer.SpeakProgress`). Only
emitted when the client asks (`GetEventInterest`), with offsets accumulating
across fragments over SAPI's one continuous stream. Because piper.exe returns no
per-word alignment, each word's audio offset is **estimated** proportionally to
its character position (`ComputeWordMarks`) — monotonic and accurate enough to
track, without the choppy prosody of synthesizing each word alone. If you ever
need frame-accurate highlighting, switch the backend to piper1-gpl and emit real
phoneme timings, or synthesize per word.

## Male + female voices (done)
`DllRegisterServer` registers **two** tokens against the one engine CLSID —
"EYEWAZ Urdu (Female)" and "EYEWAZ Urdu (Male)" — differing only by their
`Gender` and a custom **`ServerVoice`** attribute (`eyewaz-urdu-female` /
`eyewaz-urdu-male`). The engine reads `ServerVoice` from whichever token the
listener picked and passes it as `"voice"` in the POST, so the local server
synthesises the matching model. Adding another gender/accent is one more
`RegisterVoiceToken(...)` call. Verified: both enumerate with correct gender and
produce distinct audio (female 184 KB vs male 129 KB for the same sentence).

## What's still stubbed
- Verify the exact `sapi.lib` path on your SDK if CMake can't auto-find it.

## Why not embed Piper in C++?
We could (via onnxruntime + a C++ phonemizer), and that removes the local server
dependency — a good v2. For now, reusing the Python server is far less code and
guarantees identical audio to every other EYEWAZ surface.
