import os, glob, time, zipfile, subprocess, torch

VOICE      = os.getenv("VOICE", "male")          # male | female
LANG       = os.getenv("LANG_NAME", "urdu")      # urdu | punjabi (voice id eyewaz-<lang>-<gender>)
MIN_CLIPS  = int(os.getenv("MIN_CLIPS", "300"))  # guards against training an old pilot zip
NAME       = f"eyewaz-{LANG}-{VOICE}"
TAG        = VOICE if LANG == "urdu" else f"{LANG}-{VOICE}"   # urdu keeps its old paths
ESPEAK     = os.getenv("ESPEAK", "ur")
SR         = 22050
BATCH      = int(os.getenv("BATCH", "16"))
MAX_HOURS  = int(os.getenv("MAX_HOURS", "8"))
MAX_EPOCHS = int(os.getenv("MAX_EPOCHS", "2000"))
VAL_EVERY  = 5   # validation (audio samples + MOS) is the wall-clock cost, not the GPU step

WORK   = "/workspace/work"
OUT    = f"/workspace/out-{TAG}"
OUTDIR = "/workspace/final"
PT     = f"{WORK}/pretrained.ckpt"
for d in (WORK, OUT, OUTDIR):
    os.makedirs(d, exist_ok=True)

# --- dataset ---
DATA = f"{WORK}/dataset-{TAG}"
if not glob.glob(f"{DATA}/**/metadata.csv", recursive=True):
    cands = sorted(glob.glob(f"/workspace/dataset-{TAG}*.zip"))
    assert cands, f"no /workspace/dataset-{TAG}*.zip uploaded"
    zipfile.ZipFile(cands[-1]).extractall(DATA)   # -full wins over an old pilot zip
meta  = glob.glob(f"{DATA}/**/metadata.csv", recursive=True)[0]
AUDIO = os.path.dirname(meta) + "/wav"
CSV   = f"{WORK}/{TAG}.csv"
with open(meta, encoding="utf-8") as fi, open(CSV, "w", encoding="utf-8") as fo:
    for line in fi:
        line = line.strip()
        if "|" in line:
            cid, t = line.split("|", 1)
            fo.write(f"{cid}.wav|{t}\n")
nclips = len(glob.glob(AUDIO + "/*.wav"))
print("clips:", nclips, "| audio:", AUDIO, flush=True)
assert nclips > MIN_CLIPS, f"Only {nclips} clips: wrong (pilot) dataset zip, refusing to train."

# --- self-correcting loop (resume + OOM backoff + retries) ---
def latest_ckpt():
    c = sorted(glob.glob(f"{OUT}/**/*.ckpt", recursive=True), key=os.path.getmtime)
    return c[-1] if c else None

def warm_start():
    ck = torch.load(PT, map_location="cpu", weights_only=False)
    for k in ['hyper_parameters','hparams_name','datamodule_hyper_parameters','loops','callbacks']:
        ck.pop(k, None)
    ck['epoch'] = 0; ck['global_step'] = 0
    for s in (ck.get('lr_schedulers') or []):
        if isinstance(s, dict): s['last_epoch'] = 0; s['_step_count'] = 1
    p = f"{WORK}/warm.ckpt"; torch.save(ck, p); return p

deadline = time.time() + MAX_HOURS*3600
attempt = 0
while time.time() < deadline:
    resume = latest_ckpt() or warm_start()
    print(f"\n===== attempt {attempt+1} | resume {os.path.basename(resume)} | batch {BATCH} =====", flush=True)
    inner = (f"cd {WORK}/piper1 && PYTHONPATH={WORK}:{WORK}/piper1 python -m piper.train fit "
             f"--data.voice_name {NAME} --data.csv_path {CSV} --data.audio_dir {AUDIO} "
             f"--model.sample_rate {SR} --data.espeak_voice {ESPEAK} --data.cache_dir {WORK}/cache "
             f"--data.config_path {OUTDIR}/{NAME}.json --data.batch_size {BATCH} "
             f"--ckpt_path {resume} --trainer.max_epochs {MAX_EPOCHS} "
             f"--trainer.max_time 00:0{MAX_HOURS}:00:00 "
             f"--trainer.check_val_every_n_epoch {VAL_EVERY} "
             f"--trainer.default_root_dir {OUT} --trainer.accelerator gpu --trainer.devices 1")
    rc = subprocess.run(["bash","-c", f"set -o pipefail; {inner} 2>&1 | tee {WORK}/train.log"]).returncode
    if rc == 0:
        print("training completed.", flush=True); break
    log = open(f"{WORK}/train.log").read()[-4000:].lower()
    attempt += 1
    if "out of memory" in log:
        BATCH = max(4, BATCH // 2); print(f"OOM -> batch {BATCH}, resuming", flush=True)
    elif attempt >= 6:
        print("stopping after repeated failures. Tail:\n", log[-1800:], flush=True); break
    else:
        print(f"crashed (rc={rc}); resuming in 15s...", flush=True); time.sleep(15)

print("loop finished. newest ckpt:", latest_ckpt(), flush=True)

# --- export ONNX ---
# Perceived quality peaks mid-run and then drifts down on a small dataset, so the last
# checkpoint is usually NOT the best one. Export both and let the ear decide.
import re, shutil

def export(ck, name):
    onnx = f"{OUTDIR}/{name}.onnx"
    print("exporting:", ck, "->", name, flush=True)
    subprocess.run(["bash","-c",
        f"cd {WORK}/piper1 && PYTHONPATH={WORK}:{WORK}/piper1 python -m piper.train.export_onnx "
        f"--checkpoint {ck} --output-file {onnx}"])
    cfg = f"{OUTDIR}/{NAME}.json"
    if os.path.exists(cfg):
        shutil.copy(cfg, onnx + ".json")
    if os.path.exists(onnx):
        print(f"EXPORTED: {onnx} ({round(os.path.getsize(onnx)/1e6,1)} MB)", flush=True)

cks = sorted(glob.glob(f"{OUT}/**/*.ckpt", recursive=True), key=os.path.getmtime)
if cks:
    export(cks[-1], NAME)

    scored = []
    for p in glob.glob(f"{OUT}/**/epoch=*val_mos=*.ckpt", recursive=True):
        # NOT [0-9.]+ : that swallows the dot before "ckpt" and float() dies on "3.7447."
        m = re.search(r"val_mos=(\d+\.\d+)", os.path.basename(p))
        if m:
            scored.append((float(m.group(1)), p))
    if scored:
        best_mos, best_ck = max(scored)
        print(f"best val_mos: {best_mos} ({os.path.basename(best_ck)})", flush=True)
        if os.path.realpath(best_ck) != os.path.realpath(cks[-1]):
            export(best_ck, f"{NAME}-best")
print("ALL_DONE", flush=True)
