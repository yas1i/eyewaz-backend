"""
Shared Piper voice registry for EYEWAZ.

One place that answers "which voices do we have, and what does this voice id mean",
so the local server (tts-local/piper_server.py) and the cloud service
(tts-service/app.py) cannot drift apart.

A voice is a `<id>.onnx` next to its `<id>.onnx.json` (or `<id>.json`) in a voices
directory. File names follow `eyewaz-<language>-<gender>`, e.g.
`eyewaz-urdu-female.onnx`.

Every voice answers to several ids so callers can stay readable:

    eyewaz-urdu-female   the canonical id (the file name)
    urdu-female          without the product prefix
    female               bare gender, when only one voice has that gender

Nothing here imports piper or torch, so it is safe to import at module load.
"""

import json
import os
from collections import OrderedDict

GENDERS = ("female", "male")

# espeak-ng codes, matching the NVDA driver's _LANG_MAP. Regional languages that
# espeak-ng does not cover fall back to Urdu.
_LANGUAGES = {
    "urdu": "ur", "punjabi": "pa", "sindhi": "sd", "pashto": "ps",
    "bengali": "bn", "english": "en",
    "saraiki": "ur", "balochi": "ur", "kashmiri": "ur", "hindko": "ur",
}


def _tokens(voice_id):
    return voice_id.lower().replace("_", "-").split("-")


def language_of(voice_id):
    for token in _tokens(voice_id):
        if token in _LANGUAGES:
            return _LANGUAGES[token]
    return "ur"


def gender_of(voice_id):
    for token in _tokens(voice_id):
        if token in GENDERS:
            return token
    return ""


def pretty_name(voice_id):
    """'eyewaz-urdu-female' -> 'EYEWAZ Urdu (female)'."""
    parts = [p for p in _tokens(voice_id) if p]
    if parts and parts[0] == "eyewaz":
        parts = parts[1:]
    gender = gender_of(voice_id)
    words = [p for p in parts if p != gender]
    label = " ".join(w.upper() if len(w) <= 2 else w.capitalize() for w in words)
    return f"EYEWAZ {label} ({gender})".replace("  ", " ") if gender else f"EYEWAZ {label}"


def _config_for(model_path):
    for candidate in (model_path + ".json", os.path.splitext(model_path)[0] + ".json"):
        if os.path.isfile(candidate):
            return candidate
    return ""


def discover(voices_dir):
    """{canonical_id: {...}} for every .onnx in voices_dir, sorted by id.

    Voices without a config are skipped: piper needs it for phonemes and sample
    rate, so a half-installed voice would fail at synthesis time instead.
    """
    found = OrderedDict()
    if not voices_dir or not os.path.isdir(voices_dir):
        return found
    for name in sorted(os.listdir(voices_dir)):
        if not name.lower().endswith(".onnx"):
            continue
        model = os.path.join(voices_dir, name)
        config = _config_for(model)
        if not config:
            continue
        rate = 22050
        try:
            with open(config, encoding="utf-8") as fh:
                rate = int(json.load(fh).get("audio", {}).get("sample_rate", rate))
        except Exception:
            pass
        vid = os.path.splitext(name)[0]
        found[vid] = {
            "id": vid,
            "name": pretty_name(vid),
            "gender": gender_of(vid),
            "language": language_of(vid),
            "sample_rate": rate,
            "model": model,
            "config": config,
        }
    return found


def alias_map(voices):
    """{alias: canonical_id}. Ambiguous aliases are dropped, never guessed."""
    counts = {}
    for vid in voices:
        for alias in _aliases_for(vid):
            counts[alias] = counts.get(alias, 0) + 1
    aliases = {}
    for vid in voices:
        for alias in _aliases_for(vid):
            if counts[alias] == 1:
                aliases[alias] = vid
    return aliases


def _aliases_for(voice_id):
    tokens = [t for t in _tokens(voice_id) if t]
    stripped = tokens[1:] if tokens and tokens[0] == "eyewaz" else tokens
    out = {voice_id.lower(), "-".join(stripped)}
    gender = gender_of(voice_id)
    if gender:
        out.add(gender)
    return {a for a in out if a}


def resolve(requested, voices, aliases=None):
    """Canonical id for a requested voice, or None.

    Accepts a canonical id, an alias, an "sh:"-prefixed id as the app stores it,
    or a language on its own. The language form matters for compatibility: users
    who chose the self-hosted voice before it had per-gender ids have "sh:urdu"
    saved in their preferences, and that must keep speaking rather than 400.
    """
    if not requested:
        return None
    key = str(requested).strip().lower()
    if key.startswith("sh:"):
        key = key[3:]
    if not key:
        return None
    if key in voices:
        return key
    hit = (aliases if aliases is not None else alias_map(voices)).get(key)
    if hit:
        return hit
    # Language on its own ("urdu", "ur") -> that language's default voice.
    lang = _LANGUAGES.get(key) or (key if key in set(_LANGUAGES.values()) else None)
    if lang:
        same_language = OrderedDict(
            (vid, info) for vid, info in voices.items() if info["language"] == lang)
        return default_id(same_language)
    return None


def default_id(voices):
    """Female first (it is the app's historical default), else the first voice."""
    for vid, info in voices.items():
        if info["gender"] == "female":
            return vid
    return next(iter(voices), None)
