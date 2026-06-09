# Train an EYEWAZ Urdu Piper voice — turnkey (free Colab GPU)

Do this **once per voice** (female, then male). You need a clean dataset from
`prepare_dataset.py` (folder with `wav/` + `metadata.csv`). Set `VOICE=female`
or `VOICE=male`. Open Google Colab → Runtime → Change runtime type → **GPU**.

## 0. Prepare the two datasets first (on your Mac)
```bash
cd tts-train
pip install -r requirements.txt            # + ffmpeg installed
python prepare_dataset.py --in female/raw --meta female/metadata.csv --out dataset-female
python prepare_dataset.py --in male/raw   --meta male/metadata.csv   --out dataset-male
```
Zip each `dataset-*` and upload to Colab (or Google Drive).

## Colab cell 1 — install Piper training
```python
!git clone -q https://github.com/rhasspy/piper
%cd piper/src/python
!pip install -q -e .
!pip install -q -r requirements.txt
!bash build_monotonic_align.sh
```

## Colab cell 2 — settings + unzip your dataset
```python
import os
VOICE = "female"          # change to "male" for the second run
DATA = f"/content/dataset-{VOICE}"
OUT  = f"/content/train-{VOICE}"
# upload dataset-female.zip / dataset-male.zip first (Files panel), then:
!unzip -oq /content/dataset-{VOICE}.zip -d /content/
```

## Colab cell 3 — preprocess (phonemize Urdu via espeak-ng)
```python
!python -m piper_train.preprocess \
  --language ur \
  --input-dir {DATA} \
  --output-dir {OUT} \
  --dataset-format ljspeech \
  --single-speaker \
  --sample-rate 22050
```

## Colab cell 4 — get a pretrained checkpoint to fine-tune from
Fine-tuning needs far less data than training from scratch. Download a
**medium-quality** Piper checkpoint (closest available language) from the Piper
voices release page and put it at `/content/pretrained.ckpt`. (Any medium 22.05 kHz
VITS checkpoint works as a starting point.)

## Colab cell 5 — train
```python
!python -m piper_train \
  --dataset-dir {OUT} \
  --accelerator gpu --devices 1 \
  --batch-size 16 \
  --max_epochs 6000 \
  --checkpoint-epochs 5 \
  --quality medium \
  --resume_from_checkpoint /content/pretrained.ckpt
```
Watch the audio samples it logs. ~1 h of clean data fine-tunes a usable voice in
a few hours; more data / more epochs = better. Stop when samples sound good.

## Colab cell 6 — export to ONNX (this is what runs cheap)
```python
CKPT = !ls -t {OUT}/lightning_logs/version_0/checkpoints/*.ckpt | head -1
CKPT = CKPT[0]
!python -m piper_train.export_onnx {CKPT} /content/eyewaz-urdu-{VOICE}.onnx
!cp {OUT}/config.json /content/eyewaz-urdu-{VOICE}.onnx.json
print("Download:", f"eyewaz-urdu-{VOICE}.onnx", "and", f"eyewaz-urdu-{VOICE}.onnx.json")
```
Download both files. Repeat cells 2–6 with `VOICE="male"`.

## Then — send me the two `.onnx` (+ `.json`) files
I'll wire a **Piper backend** into `tts-service` so EYEWAZ serves
`EYEWAZ Urdu — Female` and `EYEWAZ Urdu — Male` from your own models (replacing
MMS), and optionally bundle them **on-device** in the Android engine for offline,
zero-cost speech.
