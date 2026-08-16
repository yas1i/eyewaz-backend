# EYEWAZ Urdu Voice — installer

A single `EyewazUrduVoiceSetup.exe` that puts the voice on a Windows machine with
no manual steps: it installs the SAPI DLL, a **no-Python** speech server, the
piper runtime and both trained voices; registers "EYEWAZ Urdu (Female)" and
"EYEWAZ Urdu (Male)" with SAPI; and starts the server hidden at every logon. The
user just runs setup, then picks the voice in **JAWS → Voices**, Narrator, Word
Read Aloud, or Control Panel → Speech.

## What the installer does
- Copies to `%ProgramFiles%\EYEWAZ Urdu Voice\`: `EyewazTts.dll`,
  `eyewaz-voice-server.exe` (frozen), `piper\` (runtime), `voices\` (.onnx).
- `regsvr32` the DLL → registers both SAPI voice tokens (`dll.cpp`).
- Creates a logon scheduled task **"EYEWAZ Urdu Voice Server"** that runs
  `start-server.vbs` — a hidden, self-locating launcher that starts the server
  on `127.0.0.1:59125` (and no-ops if it is already listening).
- Uninstall reverses all of it (stop server, delete task, `regsvr32 /u`, remove
  files).

## Build it
```powershell
# one-time prerequisites
winget install JRSoftware.InnoSetup
py -m pip install pyinstaller
..\setup.ps1                      # fetch piper.exe into the add-on runtime

# build (defaults to x64, the JAWS target)
powershell -ExecutionPolicy Bypass -File build-installer.ps1 -Arch x64 -Version 1.0.0
#  -> Output\EyewazUrduVoiceSetup.exe
```
The server is frozen with **whatever Python runs PyInstaller**, and the DLL is
picked by `-Arch`, so build on an **x64** machine (or with x64 Python) for JAWS
users. Building on Windows-on-ARM with `-Arch arm64` produces an ARM64 installer
(useful for testing on that hardware / Narrator).

## Why a local server instead of piper-in-C++
The DLL stays tiny and every EYEWAZ surface (NVDA, Chrome, Android, JAWS) speaks
through the exact same trained model. The server is frozen so end users install
nothing else. A future v2 could embed onnxruntime + a C++ phonemizer to drop the
server entirely.

## Before public release
- **Code-sign** `EyewazTts.dll` and `EyewazUrduVoiceSetup.exe` (Authenticode);
  unsigned installers trip SmartScreen and many managed JAWS environments.
- Test on a clean x64 VM with a real copy of JAWS, not just Narrator/SAPI.
