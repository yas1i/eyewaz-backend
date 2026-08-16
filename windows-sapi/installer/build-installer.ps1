<#
  Build the EYEWAZ Urdu Voice installer end to end.

    powershell -ExecutionPolicy Bypass -File build-installer.ps1 [-Arch x64] [-Version 1.0.0]

  Steps:
    1. Build the SAPI DLL (both arches) via ..\build.bat.
    2. Freeze tts-local\piper_server.py into a standalone exe with PyInstaller,
       so the target machine needs NO Python. Exe mode shells out to piper.exe,
       so piper1-gpl / torch are excluded from the freeze (small, fast).
    3. Stage the DLL, server exe, piper runtime and both voices into stage\.
    4. Compile eyewaz-voice.iss with Inno Setup -> Output\EyewazUrduVoiceSetup.exe.

  Prereqs (install once):
    winget install JRSoftware.InnoSetup
    py -m pip install pyinstaller
    ..\setup.ps1        (populates the piper runtime the voices need)

  Ship x64 for JAWS: run this on an x64 Windows box (or with x64 Python) so the
  frozen server and DLL match the users' machines. Sign Output\...Setup.exe and
  the DLL before distributing.
#>
param(
  [ValidateSet("x64","arm64")] [string]$Arch = "x64",
  [string]$Version = "1.0.0"
)
$ErrorActionPreference = "Stop"

$inst  = $PSScriptRoot
$sapi  = Split-Path $inst -Parent          # windows-sapi
$repo  = Split-Path $sapi  -Parent         # repo root (or the folder holding the siblings)
$stage = Join-Path $inst "stage"
$tts   = Join-Path $repo "tts-local"
$addon = Join-Path $repo "nvda-addon\addon\synthDrivers\eyewaz"

Write-Host "== 1/4 building the SAPI DLL ($Arch) =="
cmd /c "`"$sapi\build.bat`""
$dll = Join-Path $sapi "src\EyewazTts-$Arch.dll"
if (!(Test-Path $dll)) { throw "DLL not built: $dll" }

Write-Host "== 2/4 freezing the voice server (PyInstaller) =="
$work = Join-Path $env:TEMP "eyewaz-pyi"
Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
py -m PyInstaller --noconfirm --onefile --console --name eyewaz-voice-server `
  --paths "$tts" --hidden-import voices `
  --exclude-module piper --exclude-module torch --exclude-module numpy `
  --exclude-module onnxruntime `
  --distpath "$work\dist" --workpath "$work\build" --specpath "$work" `
  "$tts\piper_server.py"
$srvexe = Join-Path $work "dist\eyewaz-voice-server.exe"
if (!(Test-Path $srvexe)) { throw "server exe not produced" }

Write-Host "== 3/4 staging files =="
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage, "$stage\piper", "$stage\voices" | Out-Null
Copy-Item $dll    (Join-Path $stage "EyewazTts.dll")
Copy-Item $srvexe (Join-Path $stage "eyewaz-voice-server.exe")
if (!(Test-Path (Join-Path $addon "runtime\piper.exe"))) {
  throw "piper runtime missing - run ..\setup.ps1 first to fetch piper.exe"
}
Copy-Item "$addon\runtime\*"      "$stage\piper"  -Recurse -Force
Copy-Item "$addon\voices\*.onnx"      "$stage\voices" -Force
Copy-Item "$addon\voices\*.onnx.json" "$stage\voices" -Force
# Trim multi-codepoint phoneme keys so the bundled piper.exe can load the voices.
py "$inst\trim_voice_maps.py" "$stage\voices"

Write-Host "== 4/4 compiling the installer (Inno Setup) =="
$iscc = Get-ChildItem "${env:ProgramFiles(x86)}", "$env:ProgramFiles", "$env:LOCALAPPDATA\Programs" `
          -Recurse -Depth 2 -Filter ISCC.exe -ErrorAction SilentlyContinue |
          Select-Object -First 1 -ExpandProperty FullName
if (-not $iscc) { throw "ISCC.exe not found - winget install JRSoftware.InnoSetup" }
& $iscc "/DAppVersion=$Version" "$inst\eyewaz-voice.iss"

Write-Host ""
Write-Host "DONE -> $(Join-Path $inst 'Output\EyewazUrduVoiceSetup.exe')"
