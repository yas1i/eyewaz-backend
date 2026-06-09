# EYEWAZ everywhere — browser & screen-reader integrations

The same self-hosted Urdu voice (`tts-service`, `POST /tts`) powers every surface
here. One voice, many front doors.

| Surface | Folder | What it gives a blind/low-vision user | Status |
|---|---|---|---|
| **Chrome / Edge extension** | `chrome/` | Select web-page text → hear it in Urdu (right-click or `Alt+Shift+U`). | ✅ Built |
| **NVDA add-on** | `nvda/` | Makes EYEWAZ Urdu a *synthesizer* — NVDA reads the whole of Windows in Urdu. | ✅ Built |
| **Android TTS engine** | `../android-tts/` | System voice — TalkBack and every Android app speak Urdu. | ✅ Built (sideload) |
| **JAWS / Narrator / all Windows** | see below | Universal Windows voice via SAPI5. | 📋 Planned |

## How each connects
- **Chrome** → background worker fetches `/tts`, plays via an offscreen audio doc.
- **NVDA** → a `synthDriver` streams `/tts` WAV into NVDA's audio player.
- **Android** → `TextToSpeechService` streams `/tts` PCM to the OS.
All read the service URL + `X-API-Key` from a user-editable setting — no shared
secret is baked in.

## JAWS (and Narrator, Magnifier, every Windows app): the SAPI5 path
JAWS has **no Python/add-on speech API** like NVDA. The universal way to give
JAWS a new voice on Windows is **SAPI5** — register EYEWAZ as a SAPI5 voice and
*every* Windows screen reader and app can use it (JAWS, Narrator, Magnifier,
Word's Read Aloud, etc.).

That's a native **COM/C++** component (`ISpTTSEngine` + `ISpObjectToken`
registration), not a script. Concrete plan:

1. **On-device model first.** A network voice is too laggy for a system-wide
   SAPI5 engine. Bundle the trained Piper `.onnx` and run it locally
   (`piper`/`sherpa-onnx`), so synthesis is instant and offline.
2. **SAPI5 wrapper.** Implement `ISpTTSEngine::Speak` to call the local model,
   convert to the format SAPI requests, and emit word/sentence events for caret
   tracking. Register a voice token under
   `HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens\EYEWAZ-Urdu`.
3. **Installer.** Ship a small signed MSI that drops the DLL + model and writes
   the registry token. Then "EYEWAZ Urdu" appears in JAWS → Options → Voices.

This is a real but separate build (Windows, C++, code signing). **Recommendation:**
ship the **NVDA add-on now** (covers the largest free-screen-reader audience),
and schedule the SAPI5 engine next to also cover JAWS + Narrator.

> Shortcut to evaluate: some open-source projects expose Piper through SAPI5
> already. We can validate the experience with one of those before committing to
> a fully branded, signed EYEWAZ SAPI5 installer.

## A note on latency & cost
Network `/tts` is great for "read this selection / page". For *system-wide* screen
reading (NVDA/JAWS), the snappy, private, zero-cost answer is the **on-device
trained Piper voice**. That's why training your own model (`../tts-train/`) is the
keystone — it unlocks offline speech across all of these surfaces at once.
