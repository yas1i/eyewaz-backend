# EYEWAZ Urdu Voice — Android TTS engine

A native Android **text-to-speech engine** that streams from your self-hosted
EYEWAZ TTS server (`tts-service/`). Once installed and selected, **TalkBack and
every app on the phone** speak Urdu through your engine — the real accessibility
unlock for blind Urdu users.

## How it works
Android lets apps register a `TextToSpeechService`. When any app (or TalkBack)
needs speech, Android calls our `onSynthesizeText()`, which POSTs the text to
`http://<your-server>:8090/tts` (with the `X-API-Key`), gets a WAV back, and
streams its PCM samples to the system. No on-device model — the Hetzner engine
does the synthesis.

## 1. Point it at your server
Edit `app/src/main/java/ai/wajd/eyewaztts/Config.kt`:
```kotlin
const val TTS_URL = "http://167.233.35.30:8090/tts"   // your engine
const val API_KEY = "tts_Rp48FUxogcTE1NBtVs8kYB3DtkSN4wCa"
```
(For production, run the engine behind HTTPS — Caddy in `tts-service/deploy/` —
use an `https://…` URL and remove `android:usesCleartextTraffic` from the manifest.)

## 2. Build the APK (Android Studio)
1. Open Android Studio → **Open** → select the `android-tts/` folder. Let Gradle sync.
2. **Build → Build APK(s)** (or **Run** on a connected phone / emulator).
   - Debug APK lands in `app/build/outputs/apk/debug/app-debug.apk`.
3. Or from a terminal with the Android SDK installed:
   ```bash
   cd android-tts
   ./gradlew assembleDebug
   ```
   (Android Studio will create the Gradle wrapper on first sync if it's missing.)

## 3. Install on the phone
- Run from Android Studio onto a connected device, **or**
- `adb install app/build/outputs/apk/debug/app-debug.apk`, **or**
- Copy the APK to the phone and tap it (enable "install unknown apps").

## 4. Switch the phone's voice to EYEWAZ
On the phone:
1. Open the **EYEWAZ Urdu Voice** app → tap **Open Text-to-speech settings**
   (or Settings → Accessibility → Text-to-speech output).
2. **Preferred engine** → choose **EYEWAZ Urdu**.
3. **Language** → **Urdu**.
4. Tap **Listen to an example** — you should hear your engine speak.

## 5. Use it with TalkBack
Settings → Accessibility → **TalkBack** → On. TalkBack now reads the screen in
Urdu through EYEWAZ — across all apps. (You can also pick EYEWAZ as the voice in
other read-aloud apps.)

## Notes / next steps
- **Urdu-only** engine for now. Add more languages by reporting them in
  `onIsLanguageAvailable` and serving those voices from the engine.
- **Network required** (it streams from the server). For offline, ship an
  on-device model (e.g. a Piper/VITS Urdu voice) inside the app later.
- **Latency:** TalkBack sends short phrases, so it's responsive; first call after
  idle may lag while the connection warms.
- **Play Store:** this is a normal app — sign and upload like any other. Declare
  no special permissions beyond INTERNET.
