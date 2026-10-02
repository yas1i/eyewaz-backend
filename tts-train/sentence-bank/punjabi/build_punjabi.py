#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the Punjabi (Shahmukhi) recording bank and rewrite the punjabi
array in ../../recorder/scripts-extra.js.

CRITICAL invariant, same as the Urdu bank: recorder sentence ids are 1-based
indices into the array, and clips for the published ids already live in B2 at
voicebank/punjabi/<speaker>/<id>.wav. So ids 1..120 are frozen, new batches
are only APPENDED, and the script refuses to write if any already-published id
would change (--allow-reorder overrides, before a deploy only).

Usage:  python3 build_punjabi.py          # writes scripts-extra.js + script txt
        python3 build_punjabi.py --check  # dry run: validation + coverage only
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch1 import BATCH1

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRA_JS = os.path.join(HERE, "..", "..", "recorder", "scripts-extra.js")
SCRIPT_TXT = os.path.join(HERE, "recording-script-punjabi.txt")

ORIGINAL_COUNT = 120   # ids 1..120 recorded by two speakers by 3 Oct 2026; frozen forever.
BATCHES = [BATCH1]     # append new batches at the END of this list only

HEAD = "window.EYEWAZ_SCRIPTS.punjabi = ["
BLOCK = re.compile(re.escape(HEAD) + r"\n(.*?)\n\];", re.S)

ALLOWED_END = ("۔", "؟", "!")
# Perso-Arabic letters, Urdu punctuation, spaces and a few marks only.
ALLOWED = re.compile(r"^[؀-ۿݐ-ݿ\s،؟۔!]+$")
BANNED = {
    "\u2013": "en dash", "\u2014": "em dash", "-": "hyphen",
    "ݨ": "ݨ (Urdu espeak cannot read it, write ن)",
    "ي": "Arabic yeh (use ی)", "ك": "Arabic kaf (use ک)",
    "هٔ": "decomposed heh",
}

SOUNDS = {
    "ڑ": "ڑ", "ٹ": "ٹ", "ڈ": "ڈ", "ں": "ں",
    "ق": "ق", "خ": "خ", "غ": "غ", "ژ": "ژ", "ث": "ث", "ذ": "ذ", "ظ": "ظ", "ض": "ض",
    "بھ": "بھ", "پھ": "پھ", "تھ": "تھ", "ٹھ": "ٹھ", "جھ": "جھ", "چھ": "چھ",
    "دھ": "دھ", "ڈھ": "ڈھ", "کھ": "کھ", "گھ": "گھ", "ڑھ": "ڑھ",
}


def load_published():
    text = open(EXTRA_JS, encoding="utf-8").read()
    m = BLOCK.search(text)
    if not m:
        raise SystemExit("punjabi block not found in scripts-extra.js")
    body = "[" + m.group(1).rstrip().rstrip(",") + "]"
    return text, m, json.loads(body)


def validate(lines):
    errors = []
    for i, s in enumerate(lines, 1):
        if s != s.strip() or "  " in s:
            errors.append(f"{i}: stray whitespace")
        if not s.endswith(ALLOWED_END):
            errors.append(f"{i}: bad ending: {s}")
        if not ALLOWED.match(s):
            bad = sorted({c for c in s if not ALLOWED.match(c)})
            errors.append(f"{i}: non-Shahmukhi chars {bad}: {s}")
        for k, why in BANNED.items():
            if k in s:
                errors.append(f"{i}: {why}: {s}")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--allow-reorder", action="store_true")
    args = ap.parse_args()

    text, m, published = load_published()
    if len(published) < ORIGINAL_COUNT:
        raise SystemExit(f"expected >= {ORIGINAL_COUNT} published lines, found {len(published)}")

    seen = set(published[:ORIGINAL_COUNT])
    bank, dupes = list(published[:ORIGINAL_COUNT]), []
    for batch in BATCHES:
        for s in batch:
            if s in seen:
                dupes.append(s)
                continue
            seen.add(s)
            bank.append(s)

    if bank[:len(published)] != published and not args.allow_reorder:
        first = next(i for i, (a, b) in enumerate(zip(bank, published), 1) if a != b) \
            if any(a != b for a, b in zip(bank, published)) else len(bank) + 1
        raise SystemExit(f"REFUSING: published id {first} would change. Append only.")

    new_only = bank[ORIGINAL_COUNT:]
    errors = validate(new_only)
    for e in errors:
        print("ERROR", e)
    for d in dupes:
        print("dupe skipped:", d)

    words = sum(len(s.split()) for s in new_only)
    print(f"published {len(published)}, frozen {ORIGINAL_COUNT}, new {len(new_only)}, total {len(bank)}")
    print(f"new words {words}, est. {words * 0.42 / 60:.0f} min per speaker")
    joined = "\n".join(bank)
    print("coverage (whole bank):", ", ".join(f"{k} {joined.count(v)}" for k, v in SOUNDS.items()))
    if errors:
        raise SystemExit(1)
    if args.check:
        return

    body = ",\n".join("  " + json.dumps(s, ensure_ascii=False) for s in bank)
    out = text[:m.start()] + HEAD + "\n" + body + "\n];" + text[m.end():]
    open(EXTRA_JS, "w", encoding="utf-8").write(out)
    with open(SCRIPT_TXT, "w", encoding="utf-8") as f:
        for i, s in enumerate(bank, 1):
            f.write(f"{i:04d}|{s}\n")
    print("wrote", os.path.relpath(EXTRA_JS, HERE), "and", os.path.basename(SCRIPT_TXT))


if __name__ == "__main__":
    main()
