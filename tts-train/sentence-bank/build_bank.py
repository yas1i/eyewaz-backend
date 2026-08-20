#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the v2 recording sentence bank and regenerate the recorder script.

CRITICAL invariant: the recorder's sentence ids are 1-based indices into
sentences.js, and clips for ids 1..514 already live in the B2 voice bank. So
this script NEVER reorders or edits the first 514 entries; new sentences are
only APPENDED after them. Re-running is idempotent (deterministic output).

Usage:  python3 build_bank.py          # writes ../recorder/sentences.js
        python3 build_bank.py --check  # dry run: validation + coverage only
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handwritten_phonemes as hp
import handwritten_topics as ht
import numbers_ur as num

HERE = os.path.dirname(os.path.abspath(__file__))
SENTENCES_JS = os.path.join(HERE, "..", "recorder", "sentences.js")
SCRIPT_TXT = os.path.join(HERE, "recording-script-v2.txt")

ORIGINAL_COUNT = 514   # ids 1..514 are already recorded; frozen forever.


def load_original():
    text = open(SENTENCES_JS, encoding="utf-8").read()
    found = re.findall(r'^\s*"(.*)",?\s*$', text, flags=re.M)
    if len(found) < ORIGINAL_COUNT:
        raise SystemExit(f"expected at least {ORIGINAL_COUNT} entries, found {len(found)}")
    return found[:ORIGINAL_COUNT]


def systematic_numbers():
    """Formulaic sentences that walk every irregular number word and the
    calendar, rotating a few natural frames so sessions do not feel robotic."""
    out = []
    count_frames = [
        "اس سوال کا درست جواب {n} ہے۔",
        "کمرہ نمبر {n} دائیں جانب ہے۔",
        "قطار میں {n} لوگ کھڑے ہیں۔",
        "بس نمبر {n} اسٹیشن جاتی ہے۔",
        "صفحہ نمبر {n} کھول لیجیے۔",
    ]
    for i in range(0, 101):
        out.append(count_frames[i % len(count_frames)].format(n=num.words(i)))
    big = [200, 250, 300, 450, 500, 750, 900, 1000, 1500, 2000, 2500, 5000,
           7500, 10000, 15000, 25000, 50000, 75000, 100000, 250000, 500000,
           1000000, 2500000, 10000000, 15000000]
    price_frames = [
        "اس چیز کی قیمت {n} روپے ہے۔",
        "مکان کا کرایہ {n} روپے مقرر ہوا۔",
        "چندے کی مد میں {n} روپے جمع ہوئے۔",
    ]
    for i, v in enumerate(big):
        out.append(price_frames[i % len(price_frames)].format(n=num.words(v)))
    for i, o in enumerate(num.ORDINALS):
        out.append(f"وہ دوڑ میں {o} نمبر پر آیا۔" if i % 2 == 0
                   else f"عمارت کی {o} منزل پر دفتر ہے۔")
    for f in num.FRACTIONS:
        out.append(f"یہاں سے بازار {f} کلومیٹر دور ہے۔")
    return out


def systematic_time():
    out = []
    hours = ["ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو", "دس", "گیارہ", "بارہ"]
    for i, h in enumerate(hours):
        if i % 3 == 0:
            out.append(f"اس وقت {h} بجے ہیں۔")
        elif i % 3 == 1:
            out.append(f"گاڑی {h} بج کر بیس منٹ پر روانہ ہو گی۔")
        else:
            out.append(f"ملاقات کا وقت ساڑھے {h} بجے طے ہوا ہے۔")
    out += [
        "پونے چار بجے چائے کا وقفہ ہو گا۔",
        "سوا چھ بجے سورج طلوع ہوا۔",
        "دوپہر بارہ بجے دکانیں کھل جاتی ہیں۔",
        "رات گیارہ بج کر پچپن منٹ پر پیغام آیا۔",
        "صبح آٹھ بج کر دس منٹ پر حاضری لگتی ہے۔",
    ]
    return out


def systematic_dates():
    out = []
    for i, m in enumerate(num.MONTHS):
        day = [ "یکم", "پانچ", "دس", "بارہ", "پندرہ", "اٹھارہ",
                "بیس", "تئیس", "پچیس", "ستائیس", "اٹھائیس", "تیس"][i]
        out.append(f"{day} {m} کو تقریب رکھی گئی ہے۔")
    for i, m in enumerate(num.ISLAMIC_MONTHS):
        if i % 2 == 0:
            out.append(f"{m} کا چاند نظر آ گیا ہے۔")
        else:
            out.append(f"{m} کے مہینے میں یہ واقعہ پیش آیا۔")
    for d in num.WEEKDAYS:
        out.append(f"{d} کے روز بازار میں خوب رونق ہوتی ہے۔")
    out += [
        "دو ہزار چھبیس کا سال تیزی سے گزر رہا ہے۔",
        "انیس سو سینتالیس میں پاکستان معرضِ وجود میں آیا۔",
        "چودہ اگست کو جشن آزادی منایا جاتا ہے۔",
        "سالِ نو کی آمد پر منصوبے بنائے جاتے ہیں۔",
    ]
    return out


def systematic_misc():
    out = []
    for v in [5, 10, 15, 20, 25, 33, 50, 66, 75, 90, 99, 100]:
        out.append(f"سروے کے مطابق {num.words(v)} فیصد لوگ متفق ہیں۔")
    digit_words = {"0": "صفر", "1": "ایک", "2": "دو", "3": "تین", "4": "چار",
                   "5": "پانچ", "6": "چھ", "7": "سات", "8": "آٹھ", "9": "نو"}
    for s in ["0300", "0421", "9211", "786", "1122", "5060"]:
        spoken = " ".join(digit_words[c] for c in s)
        out.append(f"نمبر کے شروع کے ہندسے {spoken} ہیں۔")
    return out


# Batches are FROZEN SEGMENTS: once a batch has shipped to the recorder, its
# internal order must never change (ids are positional). Only ever append new
# batches to this list; never edit or reorder an existing batch's categories.
import handwritten_batch2 as b2

BATCH1 = [
    ("qaf", hp.QAF), ("ghain", hp.GHAIN), ("khe", hp.KHE), ("ain", hp.AIN),
    ("zhe", hp.ZHE), ("retroflex", hp.RETROFLEX), ("rra", hp.RRA),
    ("aspirates", hp.ASPIRATES), ("nasal", hp.NASAL), ("izafat", hp.IZAFAT),
    ("arabic", hp.ARABIC_LOAN), ("mixed", hp.MIXED_HEAVY),
    ("tech_ui", ht.TECH_UI), ("news", ht.NEWS_FORMAL),
    ("conversation", ht.CONVERSATION), ("questions", ht.QUESTIONS),
    ("commands", ht.COMMANDS_EXCLAM), ("weather", ht.WEATHER_NATURE),
    ("family", ht.FAMILY_HOME), ("market", ht.MARKET_FOOD),
    ("travel", ht.TRAVEL), ("health", ht.HEALTH), ("education", ht.EDUCATION),
    ("emotion", ht.EMOTION_PROSODY),
    ("numbers", systematic_numbers()), ("time", systematic_time()),
    ("dates", systematic_dates()), ("misc", systematic_misc()),
]

import handwritten_batch3 as b3
import handwritten_batch4 as b4

BATCHES = [BATCH1, b2.CATEGORIES_BATCH2, b3.CATEGORIES_BATCH3,
           b4.CATEGORIES_BATCH4]


def interleave(cats):
    """Round-robin across categories so a recording session mixes prosody
    instead of drilling one sound for half an hour. Deterministic."""
    queues = [list(sents) for _, sents in cats]
    out = []
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


def validate(sentences):
    problems = []
    seen = set()
    for i, s in enumerate(sentences):
        if s in seen:
            problems.append(f"duplicate: {s}")
        seen.add(s)
        if not s.rstrip().endswith(("۔", "؟", "!")):
            problems.append(f"bad ending [{i}]: {s}")
        if re.search(r"[–—]", s):
            problems.append(f"em/en dash [{i}]: {s}")
        if re.search(r"[A-Za-z]", s):
            problems.append(f"latin letters [{i}]: {s}")
        n_words = len(s.split())
        if not 2 <= n_words <= 24:
            problems.append(f"odd length ({n_words}w) [{i}]: {s}")
    return problems


def coverage(sentences):
    targets = {
        "ق": "qaf", "غ": "ghain", "خ": "khe", "ع": "ain", "ژ": "zhe",
        "ٹ": "tta", "ڈ": "dda", "ڑ": "rra", "ں": "nasal", "ھ": "aspirate",
        "ث": "se", "ذ": "zal", "ض": "zwad", "ظ": "zoe", "ح": "he",
    }
    text = "\n".join(sentences)
    return {name: text.count(ch) for ch, name in targets.items()}


def load_published():
    """Every sentence currently in sentences.js, in order. These ids may
    already have recordings against them, so they are all frozen."""
    text = open(SENTENCES_JS, encoding="utf-8").read()
    return re.findall(r'^\s*"(.*)",?\s*$', text, flags=re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only")
    ap.add_argument("--allow-reorder", action="store_true",
                    help="skip the published-prefix guard (ONLY safe before a "
                         "batch has been deployed to the recorder)")
    args = ap.parse_args()

    original = load_original()
    # Build batch segments in order; dedupe each against everything before it.
    seen = set(original)
    new = []
    for batch in BATCHES:
        for s in interleave(batch):
            if s not in seen:
                new.append(s)
                seen.add(s)

    problems = validate(new)
    if problems:
        print("VALIDATION PROBLEMS:")
        for p in problems:
            print("  " + p)
        raise SystemExit(1)

    bank = original + new

    # Append-only guard: everything already published keeps its exact position.
    published = load_published()
    if not args.allow_reorder and bank[:len(published)] != published:
        for i, (a, b) in enumerate(zip(published, bank)):
            if a != b:
                raise SystemExit(
                    f"REFUSING TO WRITE: published id {i+1} would change.\n"
                    f"  was: {a}\n  now: {b}\n"
                    "Published ids are frozen (recordings map to them). Append "
                    "new batches only, or pass --allow-reorder if this batch "
                    "truly never reached the recorder.")
        raise SystemExit("REFUSING TO WRITE: bank is shorter than the published file.")

    print(f"original: {len(original)}   new: {len(new)}   total: {len(bank)}")
    print("coverage (occurrences across the full bank):")
    for name, n in coverage(bank).items():
        print(f"  {name:<10} {n}")
    est_min = len(new) * 4.5 / 60   # ~4.5 s per recorded sentence
    print(f"estimated new audio per speaker: ~{est_min:.0f} minutes")

    if args.check:
        return

    with open(SENTENCES_JS, "w", encoding="utf-8") as fh:
        fh.write("// Auto-generated by sentence-bank/build_bank.py - do not edit by hand.\n")
        fh.write("// Ids 1..514 are the original recorded script and are FROZEN;\n")
        fh.write("// new sentences are appended only. Regenerate via build_bank.py.\n")
        fh.write("window.EYEWAZ_SENTENCES = [\n")
        for s in bank:
            fh.write('  "' + s + '",\n')
        fh.write("];\n")
    with open(SCRIPT_TXT, "w", encoding="utf-8") as fh:
        for i, s in enumerate(bank, 1):
            fh.write(f"{i:04d}  {s}\n")
    print(f"wrote {SENTENCES_JS}")
    print(f"wrote {SCRIPT_TXT}")


if __name__ == "__main__":
    main()
