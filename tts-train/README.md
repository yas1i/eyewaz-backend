# EYEWAZ — train our own Urdu TTS voice (cheap to run)

Goal: an Urdu voice approaching Azure quality that runs for **near-zero cost**
(CPU / on-device), so it scales to the blind community freely. We own it, it's
MIT-licensed (no MMS non-commercial limit), and dialects come from more speakers.

## The model: Piper (optimized VITS)
- Trains a **single-speaker** neural voice; exports to **ONNX** → runs fast on a
  CPU and even on-device (Android). Inference cost ≈ free.
- Urdu phonemization via **espeak-ng** (`ur`) — already supported.
- One-time training on a rented GPU (~$20–100 total). Inference forever cheap.

## The whole pipeline (and where the work is)
```
record clean Urdu speech ─▶ prepare dataset (22.05kHz, transcripts)
   (THE bottleneck)              │
                                 ▼
                          fine-tune a Piper voice on a GPU (hours–days)
                                 │
                                 ▼
                          export to model.onnx  ─▶  drop into tts-service
                                                    (and/or on-device in Android)
```

### Step 1 — Data (the only hard part)
For an Azure-ish **base voice** you want **ONE consistent speaker**, clean room,
same mic, reading **5–20+ hours** of phonetically varied Urdu — with the exact
**transcript** of every clip. See `recording-guide.md`. (Start small: even
**1–2 hours** fine-tunes a usable voice from a pretrained checkpoint; quality
climbs with more.) Dialects = repeat per native speaker later.

### Step 2 — Prepare the dataset
Put your recordings + a `metadata.csv` (LJSpeech format: `id|transcript`) and run:
```bash
pip install -r requirements.txt        # soundfile; needs ffmpeg installed
python prepare_dataset.py --in raw/ --meta metadata.csv --out dataset/
```
This resamples to 22.05 kHz mono, validates every line, and reports total
duration + clip count. Output is Piper-ready.

### Step 3 — Train (rent a GPU)
On a cloud GPU box (RunPod/Vast/Lambda, ~$0.3–0.5/hr) with Piper installed:
```bash
# 1. preprocess (phonemize + cache)
python -m piper_train.preprocess \
  --language ur --input-dir dataset/ --output-dir train/ \
  --dataset-format ljspeech --sample-rate 22050

# 2. fine-tune from a pretrained checkpoint (needs far less data than scratch)
python -m piper_train \
  --dataset-dir train/ --accelerator gpu --devices 1 \
  --batch-size 16 --max_epochs 2000 \
  --resume_from_checkpoint pretrained.ckpt \
  --checkpoint-epochs 1 --quality medium

# 3. export to ONNX
python -m piper_train.export_onnx train/lightning_logs/version_0/checkpoints/last.ckpt eyewaz-urdu.onnx
cp dataset/config.json eyewaz-urdu.onnx.json
```
(Get a pretrained checkpoint to fine-tune from the Piper voices repo — closest
available language/quality. Fine-tuning a few hundred–thousand steps on 1–2 h of
clean audio already gives a usable voice.)

### Step 4 — Serve it cheaply
- **Server:** add a Piper backend to `tts-service` (loads `eyewaz-urdu.onnx` via
  the `piper-tts` Python package) and set it as the engine — replaces MMS, same
  `/tts` API, runs on the same €4.59 CPU box.
- **On-device (best):** bundle the `.onnx` in the Android TTS-engine app so it
  speaks **offline with zero server cost**. (I can wire either; ask when you have
  a model.)

## Honest expectations
- **Data quality decides everything.** Clean, consistent single-speaker audio +
  accurate transcripts = good voice. Noisy/mismatched data = poor voice.
- **Timeline:** data collection is the long pole (weeks of recording for many
  hours); training is hours–days; iterate a couple of rounds for polish.
- **Cost:** one-time GPU rental for training; inference essentially free.
- **Dialects:** train the base voice first, then per-dialect voices from native
  speakers (reuse this pipeline + the `docs/voice-bank/` consent flow).

## What I can build when you're ready
1. The Piper backend in `tts-service` (swap MMS → your ONNX).
2. On-device Piper in the Android engine (offline, free).
3. A turnkey training script/Colab once you have ~1 h of clean audio to pilot.
