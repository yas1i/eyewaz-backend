"""
Urdu text normalization for TTS. The biggest cheap quality win for MMS: it reads
raw "123", "45%", "3.5", Arabic-Indic digits, etc. badly. We convert numbers to
spoken Urdu words (South-Asian lakh/crore system), tidy symbols and whitespace,
and ensure sentence-final punctuation so prosody/pauses sound natural.

Note: we intentionally do NOT add diacritics (اعراب) — MMS-tts-urd was trained on
undiacritized text, so adding them would hurt, not help.
"""

import re

# 0..99 in Urdu (irregular, like Hindustani).
BELOW_100 = [
    "صفر", "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو",
    "دس", "گیارہ", "بارہ", "تیرہ", "چودہ", "پندرہ", "سولہ", "سترہ", "اٹھارہ", "انیس",
    "بیس", "اکیس", "بائیس", "تئیس", "چوبیس", "پچیس", "چھبیس", "ستائیس", "اٹھائیس", "انتیس",
    "تیس", "اکتیس", "بتیس", "تینتیس", "چونتیس", "پینتیس", "چھتیس", "سینتیس", "اڑتیس", "انتالیس",
    "چالیس", "اکتالیس", "بیالیس", "تینتالیس", "چوالیس", "پینتالیس", "چھیالیس", "سینتالیس", "اڑتالیس", "انچاس",
    "پچاس", "اکیاون", "باون", "ترپن", "چون", "پچپن", "چھپن", "ستاون", "اٹھاون", "انسٹھ",
    "ساٹھ", "اکسٹھ", "باسٹھ", "تریسٹھ", "چونسٹھ", "پینسٹھ", "چھیاسٹھ", "سڑسٹھ", "اڑسٹھ", "انہتر",
    "ستر", "اکہتر", "بہتر", "تہتر", "چوہتر", "پچہتر", "چھہتر", "ستتر", "اٹھہتر", "اناسی",
    "اسی", "اکیاسی", "بیاسی", "تراسی", "چوراسی", "پچاسی", "چھیاسی", "ستاسی", "اٹھاسی", "نواسی",
    "نوے", "اکیانوے", "بانوے", "ترانوے", "چورانوے", "پچانوے", "چھیانوے", "ستانوے", "اٹھانوے", "ننانوے",
]

# Arabic-Indic (٠-٩) and Extended Arabic-Indic / Urdu (۰-۹) digits → ASCII.
_DIGIT_MAP = {ord(a): ord(b) for a, b in zip("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")}


def _int_to_words(n):
    n = int(n)
    if n == 0:
        return "صفر"
    if n < 0:
        return "منفی " + _int_to_words(-n)
    if n < 100:
        return BELOW_100[n]
    if n < 1000:
        h, r = divmod(n, 100)
        return BELOW_100[h] + " سو" + ((" " + _int_to_words(r)) if r else "")
    for div, name in ((10_000_000, "کروڑ"), (100_000, "لاکھ"), (1_000, "ہزار")):
        if n >= div:
            q, r = divmod(n, div)
            return _int_to_words(q) + " " + name + ((" " + _int_to_words(r)) if r else "")
    return str(n)  # unreachable


def _digits_one_by_one(s):
    return " ".join(BELOW_100[int(d)] for d in s if d.isdigit())


def _num_to_words(tok):
    tok = tok.replace(",", "").replace("٫", ".")
    if "." in tok:
        ip, _, fp = tok.partition(".")
        ip = ip or "0"
        words = _int_to_words(int(ip))
        if fp:
            words += " اعشاریہ " + _digits_one_by_one(fp)
        return words
    if len(tok) > 9:                     # huge run (id/phone) → read digit by digit
        return _digits_one_by_one(tok)
    return _int_to_words(int(tok))


_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalize(text):
    if not text:
        return text
    t = text.translate(_DIGIT_MAP)
    t = t.replace("%", " فیصد ").replace("٪", " فیصد ")
    t = _NUM_RE.sub(lambda m: _num_to_words(m.group(0)), t)
    t = re.sub(r"[ \t]+", " ", t).strip()
    if t and t[-1] not in "۔؟!.?،":
        t += "۔"                          # sentence-final stop helps prosody
    return t
