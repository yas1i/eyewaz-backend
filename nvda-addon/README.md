# EYEWAZ Urdu — NVDA add-on (offline)

A speech synthesizer add-on that gives **NVDA**, the free Windows screen reader,
a natural **Urdu** voice that runs **fully offline**. No internet, no per
character cost. It uses your own trained Piper neural voice, the same voice that
powers every other EYEWAZ surface.

This is the screen reader path most blind Urdu users actually use on a computer,
the same approach as Rehnuma Awaz. The C++ SAPI engine in `../windows-sapi/`
(for JAWS and Narrator) and the local server in `../tts-local/` cover the other
Windows surfaces; this add-on is the NVDA one.

## How it works

```
NVDA  --(speak Urdu)-->  synthDrivers/eyewaz.py  --(stdin text)-->  piper.exe
                                                  <--(raw PCM)------  (your .onnx)
        plays the audio through NVDA's own audio output
```

The driver shells out to a bundled `piper.exe` and streams the raw 16 bit PCM it
returns straight into NVDA's audio player. Running Piper as a small subprocess
keeps it independent of NVDA's exact Python build, so the add-on keeps working
across NVDA versions.

## Build the add-on (on your Mac or on Windows)

The package ships with the driver but **not** the binaries (the Piper runtime and
your voice models). Add those, then zip it.

1. **Fetch the Piper runtime** (Windows, in PowerShell, from this folder):
   ```powershell
   .\setup.ps1
   ```
   This downloads `piper.exe` + its DLLs + `espeak-ng-data` into
   `addon\synthDrivers\eyewaz\runtime`.

2. **Add your trained voices.** Copy the files the trainer produced into
   `addon/synthDrivers/eyewaz/voices/`, for example:
   ```
   eyewaz-urdu-female.onnx
   eyewaz-urdu-female.onnx.json
   eyewaz-urdu-male.onnx
   eyewaz-urdu-male.onnx.json
   ```

3. **Package it:**
   ```bash
   python build.py
   ```
   This writes `EyewazUrdu-1.0.0.nvda-addon`.

## Install and select the voice (on Windows)

1. With NVDA running, open the `.nvda-addon` file (or NVDA menu, Tools, Add-on
   store, Install from external source). Restart NVDA when asked.
2. NVDA menu, Preferences, Settings, **Speech**.
3. **Synthesizer**, choose **EYEWAZ Urdu Voice**.
4. **Voice**, choose **EYEWAZ Urdu Female** or **EYEWAZ Urdu Male**.
5. Adjust **Rate** and **Volume** as usual. NVDA now reads everything in Urdu.

## Notes

- The voice only appears once both the runtime and at least one `.onnx` voice are
  present. Before then the synthesizer is hidden, by design.
- Speed maps to Piper's length scale (NVDA rate 0 is slow, 100 is fast).
- Everything runs on the device. The add-on opens no network connections.
- Built by Yasir Musawar, WAJD AI. https://www.eyewaz.com
