#!/usr/bin/env python3
"""
Prepare a recording set for Piper training.

Reads raw WAVs + a metadata.csv ("id|transcript" per line), resamples every clip
to 22.05 kHz mono 16-bit (via ffmpeg), validates that each line has matching
audio + non-empty text, and writes a clean Piper-ready dataset. Prints the total
duration and clip count so you know how much data you have.

Usage:
  python prepare_dataset.py --in raw/ --meta metadata.csv --out dataset/
Requires: ffmpeg on PATH, and `pip install soundfile`.
"""

import argparse
import os
import subprocess
import sys

import soundfile as sf

SR = 22050


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", required=True, help="folder of raw .wav files")
    ap.add_argument("--meta", required=True, help="metadata.csv with lines: id|transcript")
    ap.add_argument("--out", required=True, help="output dataset folder")
    args = ap.parse_args()

    wav_out = os.path.join(args.out, "wav")
    os.makedirs(wav_out, exist_ok=True)

    kept, skipped, total_secs = 0, 0, 0.0
    out_lines = []

    with open(args.meta, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or "|" not in line:
                continue
            cid, text = line.split("|", 1)
            cid, text = cid.strip(), text.strip()
            src = os.path.join(args.indir, cid + ".wav")
            if not text:
                print(f"  skip {cid}: empty transcript"); skipped += 1; continue
            if not os.path.exists(src):
                print(f"  skip {cid}: missing {src}"); skipped += 1; continue

            dst = os.path.join(wav_out, cid + ".wav")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
                     "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", dst],
                    check=True,
                )
                info = sf.info(dst)
                dur = info.frames / float(info.samplerate)
            except Exception as e:
                print(f"  skip {cid}: ffmpeg/read failed ({e})"); skipped += 1; continue

            if dur < 0.6 or dur > 15:
                print(f"  note {cid}: {dur:.1f}s (aim 2–12s)")
            total_secs += dur
            out_lines.append(f"{cid}|{text}")
            kept += 1

    with open(os.path.join(args.out, "metadata.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    mins = total_secs / 60.0
    print("\n=== EYEWAZ dataset ===")
    print(f"clips kept     : {kept}")
    print(f"clips skipped  : {skipped}")
    print(f"total duration : {mins:.1f} min ({total_secs/3600:.2f} h)")
    print(f"output         : {args.out}/  (wav/ + metadata.csv)")
    if mins < 30:
        print("note: < 30 min — fine for a quick pilot; collect more for quality.")
    if kept == 0:
        sys.exit("No usable clips — check paths and metadata.csv format (id|transcript).")


if __name__ == "__main__":
    main()
