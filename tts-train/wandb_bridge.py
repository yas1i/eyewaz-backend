"""Streams TensorBoard scalars from the piper training run to W&B, read-only.
Runs beside training; killing or crashing it never affects the trainer."""
import os, glob, time, wandb
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

VOICE = os.getenv("VOICE", "male")
LANG = os.getenv("LANG_NAME", "urdu")
TAG = VOICE if LANG == "urdu" else f"{LANG}-{VOICE}"   # must match train_vast.py
OUT = f"/workspace/out-{TAG}"
run = wandb.init(project="eyewaz-tts", entity="wajd-ai",
                 name=f"{LANG}-{VOICE}-4090-vast", id=f"{LANG}-{VOICE}-4090-vast",
                 resume="allow")
print("W&B run:", run.url, flush=True)

seen = set()
while True:
    try:
        dirs = {os.path.dirname(p) for p in
                glob.glob(f"{OUT}/**/events.out.tfevents*", recursive=True)}
        for d in sorted(dirs):
            acc = EventAccumulator(d, size_guidance={'scalars': 0})
            acc.Reload()
            for tag in acc.Tags().get('scalars', []):
                for s in acc.Scalars(tag):
                    key = (d, tag, s.step)
                    if key in seen:
                        continue
                    seen.add(key)
                    wandb.log({tag: s.value}, step=s.step)
    except Exception as e:
        print("bridge warn:", e, flush=True)
    time.sleep(30)
