# EYEWAZ online voice bank — collect & train many languages

Scale voice collection beyond one laptop: native speakers across provinces record
in the browser, clips upload to the server, and you export a **training-ready
dataset** per language/speaker that drops straight into the Kaggle/Colab notebook.

```
recordist (browser /record)  ──upload──►  /api/voicebank/clip  ──►  server storage
                                                                      (voicebank/<lang>/<speaker>/NNNN.wav + DB)
        you ──►  /api/voicebank/export?lang=…  ──►  dataset-<lang>.zip  ──►  EYEWAZ_train.ipynb  ──►  .onnx
```

## Collect
- Share **`https://eyewaz.com/record`** with a recordist in each region.
- They pick **Province/dialect + Voice + Speaker**, tick **consent**, open the
  **“Upload to EYEWAZ server”** box and set **Server URL = https://eyewaz.com**
  (+ the voice-bank key if you set one), then record the script line by line.
- Each saved clip writes locally *and* uploads to the bank (`+ uploaded ☁`).
- Desktop Chrome/Edge (the recorder needs the File System Access API).

## API
| Endpoint | Who | What |
|---|---|---|
| `POST /api/voicebank/clip` | recordists | one clip + lang/speaker/gender/sentence_id/transcript/consent |
| `GET /api/voicebank/stats` | anyone | clips + minutes per language and per speaker |
| `GET /api/voicebank/export?lang=&speaker=&key=` | you (DEV_PLAN_KEY) | dataset `.zip` (NNNN.wav + metadata.csv) |

**Env**
- `VOICEBANK_KEY` (optional) — if set, uploads must include it (`X-VoiceBank-Key`
  header or `key` form field). Hand it only to trusted recordists.
- `DEV_PLAN_KEY` — required to export datasets. Keep unset/secret in prod.

Consent is **always** required on upload; each clip stores `consent_at` +
contributor.

## Check progress
```
curl https://eyewaz.com/api/voicebank/stats
# { "languages": { "punjabi": {clips, minutes, speakers}, ... }, "total_minutes": … }
```

## Export → train
```
curl -o dataset-punjabi.zip "https://eyewaz.com/api/voicebank/export?lang=punjabi&key=YOUR_DEV_PLAN_KEY"
```
Upload that zip to Kaggle/Colab and run **`tts-train/EYEWAZ_train.ipynb`** with
`VOICE='punjabi'` and the matching `--data.espeak_voice` (e.g. `pa` Punjabi,
`ps` Pashto, `sd` Sindhi, `ur` Urdu). Out comes `eyewaz-urdu-<lang>.onnx`, which
wires into every EYEWAZ surface (tts-local, NVDA, JAWS/SAPI, Chrome, Android,
cloud).

## Aim per voice
- **Pilot:** ~6 min (proves the pipeline; rough).
- **Good:** 30–60+ min per speaker, clean and consistent.

## Roadmap (not yet built)
- **Upload-only mode** so contributors on phones (no local folder / File System
  Access) can record and submit.
- A small **admin dashboard** at `/record` showing `stats` live.
- One-click **“export + launch training”** that kicks a cloud GPU job (today the
  GPU step is the Kaggle/Colab notebook — the server can’t train on CPU).
