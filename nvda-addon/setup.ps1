# EYEWAZ Urdu NVDA add-on, runtime fetcher.
# Downloads the Piper Windows runtime (piper.exe + DLLs + espeak-ng-data) into
# addon\synthDrivers\eyewaz\runtime so the add-on can synthesize offline.
#
# Run from this folder in PowerShell:
#   .\setup.ps1
#
# The voice models (.onnx + .onnx.json) are separate, drop them into
# addon\synthDrivers\eyewaz\voices (see PUT-VOICES-HERE.txt).

param(
    # Pin a known good Piper Windows release. Bump if a newer build is needed.
    [string]$PiperVersion = "2023.11.14-2",
    [string]$PiperAsset   = "piper_windows_amd64.zip"
)

$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtime = Join-Path $root "addon\synthDrivers\eyewaz\runtime"
$tmpZip  = Join-Path $env:TEMP "piper_windows.zip"
$tmpDir  = Join-Path $env:TEMP "piper_windows_extract"

$url = "https://github.com/rhasspy/piper/releases/download/$PiperVersion/$PiperAsset"

Write-Host "Downloading Piper runtime:" $url
Invoke-WebRequest -Uri $url -OutFile $tmpZip

if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

# The archive contains a top level "piper" folder. Copy its contents into runtime.
$src = Join-Path $tmpDir "piper"
if (-not (Test-Path $src)) { $src = $tmpDir }

New-Item -ItemType Directory -Force -Path $runtime | Out-Null
Copy-Item -Path (Join-Path $src "*") -Destination $runtime -Recurse -Force

Remove-Item -Force $tmpZip
Remove-Item -Recurse -Force $tmpDir

$piperExe = Join-Path $runtime "piper.exe"
if (Test-Path $piperExe) {
    Write-Host "Piper runtime installed in" $runtime
    Write-Host "Next: drop your .onnx voices into addon\synthDrivers\eyewaz\voices, then run build.py"
} else {
    Write-Warning "piper.exe was not found after extraction. Check the release asset name."
}
