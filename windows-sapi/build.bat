@echo off
REM Build the EYEWAZ SAPI5 voice DLL for BOTH architectures with MSVC.
REM
REM Requires "Build Tools for Visual Studio 2022" with the "Desktop development
REM with C++" workload (VCTools + Windows SDK). ATL is NOT needed - the engine
REM uses Microsoft::WRL::ComPtr from the Windows SDK, not ATL's CComPtr.
REM
REM Produces, in src\:
REM   EyewazTts-arm64.dll   (Windows on ARM screen readers / Narrator)
REM   EyewazTts-x64.dll     (JAWS and every 64-bit SAPI host)
REM
REM Register (elevated):   regsvr32 src\EyewazTts-x64.dll
REM Then pick "EYEWAZ Urdu" in JAWS > Voices, Narrator, or Control Panel > Speech.
REM The voice speaks by POSTing to the local piper server on 127.0.0.1:59125
REM (see ..\tts-local\piper_server.py --piper-exe ... --model ...).

setlocal enabledelayedexpansion
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath`) do set VSPATH=%%i
if not defined VSPATH (
  echo Could not locate Visual Studio. Install the C++ Build Tools first.
  exit /b 1
)
set VCVARS="!VSPATH!\VC\Auxiliary\Build\vcvarsall.bat"
cd /d "%~dp0src"

set CLFLAGS=/nologo /LD /EHsc /std:c++17 /DUNICODE /D_UNICODE /DWIN32_LEAN_AND_MEAN
set LINKLIBS=winhttp.lib ole32.lib oleaut32.lib advapi32.lib sapi.lib

echo ==== ARM64 ====
REM "arm64" native on an ARM64 host; use "x64" if you build on an x64 host.
call !VCVARS! arm64 >nul 2>&1 || call !VCVARS! x64_arm64 >nul
cl %CLFLAGS% EyewazTtsEngine.cpp dll.cpp /Fe:EyewazTts-arm64.dll /link /DEF:EyewazTts.def %LINKLIBS%

echo ==== X64 ====
REM cross-compile to x64; "arm64_amd64" on an ARM64 host, "x64" on an x64 host.
call !VCVARS! arm64_amd64 >nul 2>&1 || call !VCVARS! x64 >nul
cl %CLFLAGS% EyewazTtsEngine.cpp dll.cpp /Fe:EyewazTts-x64.dll /link /DEF:EyewazTts.def %LINKLIBS%

echo ==== RESULT ====
dir *.dll
endlocal
