#!/usr/bin/env python3
"""
Package the EYEWAZ Urdu NVDA add-on into a .nvda-addon file (a zip NVDA installs).

The contents of addon/ become the root of the package, so the zip holds
manifest.ini, synthDrivers/eyewaz.py and the bundled runtime + voices.

Usage:
  python build.py                 # -> EyewazUrdu-<version>.nvda-addon
  python build.py --out dist/     # write into a folder

Run setup.ps1 first (to fetch piper.exe) and drop your .onnx voices into
addon/synthDrivers/eyewaz/voices/, otherwise the package will install but the
voice will not appear until those files are present.
"""

import argparse
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.join(HERE, "addon")

# Files we never want inside the package.
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = (".pyc",)


def _voice_config_for_runtime(path):
    """Return the .onnx.json bytes with multi-codepoint phonemes dropped.

    The voices are trained with piper1-gpl, whose phoneme_id_map keeps the
    espeak diphthongs carried over from the English warm-start (aɪ, aʊ, ɔɪ,
    eɪ, oʊ) as single two-codepoint tokens. The bundled rhasspy piper.exe
    validates that every map key is a single codepoint and refuses to load a
    voice that has any, so it must never see them. Urdu (espeak ur) does not
    emit these English diphthongs, so dropping them is safe for this runtime
    while the training masters keep the full map for the piper1-gpl server.
    """
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    id_map = cfg.get("phoneme_id_map")
    if isinstance(id_map, dict):
        cfg["phoneme_id_map"] = {k: v for k, v in id_map.items() if len(k) == 1}
    return json.dumps(cfg, ensure_ascii=False).encode("utf-8")


def _manifest_version():
    path = os.path.join(ADDON_DIR, "manifest.ini")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip().lower().startswith("version"):
                return line.split("=", 1)[1].strip()
    return "0.0.0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=HERE, help="output folder")
    args = ap.parse_args()

    if not os.path.isfile(os.path.join(ADDON_DIR, "manifest.ini")):
        sys.exit("addon/manifest.ini not found, run this from the nvda-addon folder")

    version = _manifest_version()
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, f"EyewazUrdu-{version}.nvda-addon")

    have_piper = os.path.isfile(
        os.path.join(ADDON_DIR, "synthDrivers", "eyewaz", "runtime", "piper.exe")
    )
    voices_dir = os.path.join(ADDON_DIR, "synthDrivers", "eyewaz", "voices")
    have_voice = any(f.lower().endswith(".onnx") for f in os.listdir(voices_dir)) \
        if os.path.isdir(voices_dir) else False

    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _dirs, files in os.walk(ADDON_DIR):
            for name in files:
                if name in SKIP_NAMES or name.endswith(SKIP_SUFFIXES):
                    continue
                full = os.path.join(base, name)
                arc = os.path.relpath(full, ADDON_DIR)
                if name.lower().endswith(".onnx.json"):
                    z.writestr(arc, _voice_config_for_runtime(full))
                else:
                    z.write(full, arc)
                count += 1

    print(f"Built {out_path}")
    print(f"  files: {count}   version: {version}")
    if not have_piper:
        print("  warning: piper.exe is missing, run setup.ps1 before shipping")
    if not have_voice:
        print("  warning: no .onnx voice in voices/, the voice will not appear yet")
    print("Install: open the file on Windows with NVDA running, or NVDA menu ->")
    print("Tools -> Add-on store -> Install from external source.")


if __name__ == "__main__":
    main()
