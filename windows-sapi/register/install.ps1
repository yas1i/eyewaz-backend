# Install / uninstall the EYEWAZ SAPI5 voice. Run in an ELEVATED PowerShell.
#   .\install.ps1            # register the DLL (creates the voice token)
#   .\install.ps1 -Uninstall # remove it
param([switch]$Uninstall)

$dll = Join-Path $PSScriptRoot "..\build\Release\EyewazTts.dll"
if (-not (Test-Path $dll)) { Write-Error "Build the DLL first (see ../README.md). Missing: $dll"; exit 1 }

if ($Uninstall) {
    regsvr32 /u /s $dll
    Write-Host "EYEWAZ Urdu voice unregistered."
} else {
    regsvr32 /s $dll
    Write-Host "EYEWAZ Urdu voice registered."
    Write-Host "Start the local voice server first:  python ..\..\tts-local\piper_server.py --model <voice>.onnx"
    Write-Host "Then pick 'EYEWAZ Urdu' in JAWS / Narrator / Windows Speech settings."
}
