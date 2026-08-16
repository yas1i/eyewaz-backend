#!/usr/bin/env python3
"""Strip multi-codepoint phoneme_id_map keys from staged .onnx.json voice configs.

The bundled rhasspy piper.exe validates that every phoneme_id_map key is a single
codepoint and refuses to load a voice that carries the English diphthongs
(aɪ aʊ ɔɪ eɪ oʊ) the piper1-gpl training left in the map. Urdu never emits them,
so dropping them makes the staged voices load. build.py already does this inside
the .nvda-addon zip; the SAPI installer stages raw files, so it calls this.

    python trim_voice_maps.py <voices-dir>      (default: stage/voices)
"""
import glob
import json
import os
import sys

voices_dir = sys.argv[1] if len(sys.argv) > 1 else "stage/voices"
for path in glob.glob(os.path.join(voices_dir, "*.onnx.json")):
    cfg = json.load(open(path, encoding="utf-8"))
    id_map = cfg.get("phoneme_id_map")
    if isinstance(id_map, dict):
        before = len(id_map)
        cfg["phoneme_id_map"] = {k: v for k, v in id_map.items() if len(k) == 1}
        json.dump(cfg, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"trimmed {path}: {before} -> {len(cfg['phoneme_id_map'])}")
