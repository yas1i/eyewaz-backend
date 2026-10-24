"""
Gurmukhi to Shahmukhi transliteration, so our Punjabi voice can read Punjabi.

Azure translates into Punjabi only in Gurmukhi script, and offers no
Gurmukhi to Shahmukhi conversion. Our Punjabi voice was trained on Shahmukhi
(Perso-Arabic) text, so this converts letter by letter.

The output is meant to be SPOKEN: it spells each word by its sound, the way the
voice reads it. Loan words keep their sound but not always their usual
Shahmukhi spelling (Gurmukhi does not record which of س ث ص was meant).
"""

import re
import unicodedata

_NUKTA = "਼"
_VIRAMA = "੍"
_ADDAK = "ੱ"
_NASALS = ("ਂ", "ੰ")          # bindi, tippi

_CONSONANTS = {
    "ਕ": "ک", "ਖ": "کھ", "ਗ": "گ", "ਘ": "گھ", "ਙ": "ن",
    "ਚ": "چ", "ਛ": "چھ", "ਜ": "ج", "ਝ": "جھ", "ਞ": "ن",
    "ਟ": "ٹ", "ਠ": "ٹھ", "ਡ": "ڈ", "ਢ": "ڈھ", "ਣ": "ن",
    "ਤ": "ت", "ਥ": "تھ", "ਦ": "د", "ਧ": "دھ", "ਨ": "ن",
    "ਪ": "پ", "ਫ": "پھ", "ਬ": "ب", "ਭ": "بھ", "ਮ": "م",
    "ਯ": "ی", "ਰ": "ر", "ਲ": "ل", "ਵ": "و", "ੜ": "ڑ",
    "ਸ": "س", "ਹ": "ہ",
}
# consonant + nukta (NFD splits the precomposed ones into these pairs)
_WITH_NUKTA = {"ਸ": "ش", "ਖ": "خ", "ਗ": "غ", "ਜ": "ز", "ਫ": "ف", "ਲ": "ل"}

# independent vowels: (word start, after another vowel)
_VOWELS = {
    "ਅ": ("ا", "ا"), "ਆ": ("آ", "ا"), "ਇ": ("ای", "ئ"), "ਈ": ("ای", "ئی"),
    "ਉ": ("او", "ؤ"), "ਊ": ("او", "ؤ"), "ਏ": ("اے", "ئے"), "ਐ": ("اے", "ئے"),
    "ਓ": ("او", "و"), "ਔ": ("او", "و"), "ੲ": ("ا", "ا"), "ੳ": ("ا", "ا"),
}

# vowel signs: (inside a word, at the end of a word)
_SIGNS = {
    "ਾ": ("ا", "ا"),     # aa
    "ਿ": ("", "ی"),      # i, unwritten inside a word
    "ੀ": ("ی", "ی"),     # ii
    "ੁ": ("", "و"),      # u, unwritten inside a word
    "ੂ": ("و", "و"),     # uu
    "ੇ": ("ی", "ے"),     # e
    "ੈ": ("ی", "ے"),     # ai
    "ੋ": ("و", "و"),     # o
    "ੌ": ("و", "و"),     # au
}

_PUNCT = {"।": "۔", "॥": "۔", ",": "،", "?": "؟", ";": "؛"}
_DIGITS = {chr(0x0A66 + i): str(i) for i in range(10)}

_GURMUKHI = re.compile(r"[਀-੿]")


def has_gurmukhi(text):
    return bool(_GURMUKHI.search(text or ""))


def _is_letter(ch):
    return ch in _CONSONANTS or ch in _VOWELS


def _word(w):
    out, i, n = [], 0, len(w)
    while i < n:
        ch = w[i]
        nxt = w[i + 1] if i + 1 < n else ""
        if ch in _CONSONANTS:
            if nxt == _NUKTA and ch in _WITH_NUKTA:
                out.append(_WITH_NUKTA[ch]); i += 2
                continue
            out.append(_CONSONANTS[ch])
        elif ch == _VIRAMA:
            # subjoined ha marks aspiration (ਨ੍ਹ -> نھ); other subjoined letters
            # are written in full
            if nxt == "ਹ":
                out.append("ھ"); i += 2
                continue
        elif ch in _VOWELS:
            start = i == 0 or not (_is_letter(w[i - 1]) or w[i - 1] in _SIGNS)
            out.append(_VOWELS[ch][0 if start else 1])
        elif ch in _SIGNS:
            rest = w[i + 1:]
            final = not any(_is_letter(c) for c in rest)
            nasal_end = final and any(c in _NASALS for c in rest)
            if ch == "\u0a3f" and final:
                # ਕਿ -> کہ; elsewhere a word-final short i is not written (ਸਤਿ -> ست)
                out.append("ہ" if i == 1 else "")
            elif nasal_end and ch in ("\u0a47", "\u0a48"):
                out.append("ی")        # ਕਿਵੇਂ -> کویں, ਮੈਂ -> میں (ے never precedes ں)
            else:
                out.append(_SIGNS[ch][1 if final else 0])
        elif ch in _NASALS:
            final = not any(_is_letter(c) for c in w[i + 1:])
            if nxt in ("ਨ", "ਮ"):
                pass                      # tippi before ਨ/ਮ doubles it: ਧੰਨ -> دھن
            else:
                out.append("ں" if final else "ن")
        elif ch in (_ADDAK, _NUKTA):
            pass                          # gemination / stray nukta: unwritten
        elif ch in _DIGITS:
            out.append(_DIGITS[ch])
        else:
            out.append(_PUNCT.get(ch, ch))
        i += 1
    return "".join(out)


def to_shahmukhi(text):
    """Gurmukhi Punjabi -> Shahmukhi. Anything that is not Gurmukhi passes through."""
    if not text:
        return text
    text = unicodedata.normalize("NFD", text)
    # the danda (U+0964) sits outside the Gurmukhi block but ends Punjabi sentences
    return "".join(_word(tok) if (has_gurmukhi(tok) or "\u0964" in tok) else tok
                   for tok in re.split(r"(\s+)", text))
