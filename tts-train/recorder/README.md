# EYEWAZ Voice Recorder

A zero-install browser tool to record the training script **line by line**. It
writes `0001.wav, 0002.wav, …` plus `metadata.csv` straight into a folder you
pick — the exact input `../prepare_dataset.py` expects. No upload, all local.

## Open it
Use **Chrome or Edge** (it uses the File System Access API to save files).
```bash
# from the repo root, easiest is a tiny local server:
cd tts-train/recorder
python3 -m http.server 8000
# then open  http://localhost:8000/  in Chrome
```
(Double-clicking `index.html` also works in most Chrome setups.)

## Record
1. Pick **Speaker = Female**, click **Choose / create a folder** → make an empty
   folder called `female`. (Do the **male** pass later into a `male` folder.)
2. For each line: **Record** (or <kbd>Space</kbd>) → read the sentence → **Stop**
   → it plays back → **Save & next** (<kbd>Enter</kbd>). Fluffed it? **Re-record**
   (<kbd>R</kbd>).
3. Keyboard: <kbd>Space</kbd> record/stop · <kbd>P</kbd> play · <kbd>Enter</kbd>
   save & next · <kbd>R</kbd> re-record · <kbd>←</kbd>/<kbd>→</kbd> move.

It **remembers progress**: reopen, pick the same folder, and it resumes at the
first unrecorded line (already-recorded lines are ticked).

## Tips for a good voice
- **Quiet room**, no fan/echo. Mic about a hand's width away, slightly off to the
  side (avoids popping).
- Read **naturally and consistently** — same pace, tone, and distance every clip.
- Aim **2–12 seconds** per line (the tool warns if a take is very short/long).
- One voice per folder. Record the **whole** script with the female speaker, then
  again with the male speaker.
- Mic processing (echo cancel / noise suppression / auto-gain) is **off** on
  purpose — cleaner for training.

## Then hand it to training
```bash
cd tts-train
python prepare_dataset.py --in female --meta female/metadata.csv --out dataset-female
python prepare_dataset.py --in male   --meta male/metadata.csv   --out dataset-male
```
That resamples to 22.05 kHz mono and reports total duration. Then follow
`train_colab.md`. Send me the two `dataset-*` folders (or the trained `.onnx`)
and I'll wire the voice into every EYEWAZ surface.

## Note
Clips are saved at your mic's native sample rate (e.g. 48 kHz); `prepare_dataset`
resamples to 22.05 kHz, so you don't need to set anything.
