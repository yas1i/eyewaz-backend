"""
Online voice bank — collect recordings for many languages/dialects and export
training-ready datasets.

Native speakers (across provinces) record with the web recorder, which uploads
each clip here. Clips are stored on the server, grouped by language + speaker.
The export endpoint packages a speaker/dialect set into the exact layout
``tts-train/prepare_dataset.py`` and the training notebook consume
(``NNNN.wav`` + ``metadata.csv``), so collection → training is one click.

Endpoints
  POST /api/voicebank/clip      multipart: audio + lang,speaker,gender,sentence_id,transcript,consent
  GET  /api/voicebank/stats     -> counts + duration per language/speaker
  GET  /api/voicebank/export    ?lang=&speaker=  (DEV_PLAN_KEY) -> dataset .zip

Write protection: if VOICEBANK_KEY is set, uploads must send it (header
``X-VoiceBank-Key`` or form ``key``). Consent is always required.
"""

import io
import json
import os
import re
import zipfile
from datetime import datetime

from flask import Response, request, send_file
from flask_restful import Resource

import storage
from database.models import VoiceClip

VB_DIR = os.path.join(storage.UPLOAD_DIR, "voicebank")
os.makedirs(VB_DIR, exist_ok=True)


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-") or "anon"


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _duration(path):
    try:
        import soundfile as sf
        info = sf.info(path)
        return round(info.frames / float(info.samplerate), 3)
    except Exception:
        return 0.0


class VoiceBankClipAPI(Resource):
    """Receive one recorded utterance and store it."""

    def post(self):
        key = os.getenv("VOICEBANK_KEY")
        if key and request.headers.get("X-VoiceBank-Key") != key and request.form.get("key") != key:
            return _resp({"message": "Invalid voice-bank key."}, 401)
        if request.form.get("consent") not in ("true", "1", "yes", "on"):
            return _resp({"message": "Speaker consent is required."}, 400)
        if "audio" not in request.files:
            return _resp({"message": "No audio uploaded."}, 400)

        lang = _slug(request.form.get("lang", "urdu"))
        speaker = _slug(request.form.get("speaker", ""))
        gender = (request.form.get("gender", "") or "").lower()
        sentence_id = re.sub(r"[^0-9A-Za-z_-]", "", request.form.get("sentence_id", "") or "")
        transcript = (request.form.get("transcript", "") or "").strip()
        contributor = (request.form.get("contributor", "") or "").strip()[:160]
        if not (speaker and sentence_id and transcript):
            return _resp({"message": "Missing speaker, sentence_id or transcript."}, 400)

        rel_dir = os.path.join("voicebank", lang, speaker)
        abs_dir = os.path.join(storage.UPLOAD_DIR, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        fname = f"{sentence_id}.wav"
        abs_path = os.path.join(abs_dir, fname)
        request.files["audio"].save(abs_path)

        dur = _duration(abs_path)
        # One clip per (lang, speaker, sentence_id): re-recording replaces it.
        VoiceClip.objects(lang=lang, speaker=speaker, sentence_id=sentence_id).delete()
        VoiceClip(
            lang=lang, speaker=speaker, gender=gender, sentence_id=sentence_id,
            transcript=transcript, filename=os.path.join(rel_dir, fname),
            duration=dur, consent_at=datetime.utcnow(), contributor=contributor,
        ).save()
        return _resp({"ok": True, "lang": lang, "speaker": speaker,
                      "sentence_id": sentence_id, "duration": dur}, 200)


class VoiceBankDoneAPI(Resource):
    """Sentence ids a speaker has already uploaded — lets the recorder resume
    across sessions/devices in online-only (no local folder) mode."""

    def get(self):
        key = os.getenv("VOICEBANK_KEY")
        if key and request.headers.get("X-VoiceBank-Key") != key and request.args.get("key") != key:
            return _resp({"message": "Invalid voice-bank key."}, 401)
        lang = _slug(request.args.get("lang", ""))
        speaker = _slug(request.args.get("speaker", ""))
        if not (lang and speaker):
            return _resp({"message": "lang and speaker required."}, 400)
        ids = sorted(c.sentence_id for c in VoiceClip.objects(lang=lang, speaker=speaker))
        return _resp({"ids": ids}, 200)


class VoiceBankStatsAPI(Resource):
    """How much has been collected, by language and speaker."""

    def get(self):
        langs, speakers = {}, {}
        total_secs = 0.0
        for c in VoiceClip.objects():
            langs.setdefault(c.lang, {"clips": 0, "seconds": 0.0, "speakers": set()})
            langs[c.lang]["clips"] += 1
            langs[c.lang]["seconds"] += c.duration or 0
            langs[c.lang]["speakers"].add(c.speaker)
            sk = f"{c.lang}/{c.speaker}"
            speakers.setdefault(sk, {"clips": 0, "seconds": 0.0, "gender": c.gender})
            speakers[sk]["clips"] += 1
            speakers[sk]["seconds"] += c.duration or 0
            total_secs += c.duration or 0
        langs_out = {k: {"clips": v["clips"], "minutes": round(v["seconds"] / 60, 1),
                         "speakers": len(v["speakers"])} for k, v in langs.items()}
        speakers_out = {k: {"clips": v["clips"], "minutes": round(v["seconds"] / 60, 1),
                            "gender": v["gender"]} for k, v in speakers.items()}
        return _resp({"languages": langs_out, "speakers": speakers_out,
                      "total_minutes": round(total_secs / 60, 1)}, 200)


class VoiceBankExportAPI(Resource):
    """Package a speaker/language set into a training-ready dataset zip."""

    def get(self):
        secret = os.getenv("DEV_PLAN_KEY")
        if not secret or request.args.get("key") != secret:
            return _resp({"message": "Export requires the owner key."}, 401)
        lang = _slug(request.args.get("lang", ""))
        speaker = request.args.get("speaker")
        q = VoiceClip.objects(lang=lang)
        if speaker:
            q = q.filter(speaker=_slug(speaker))
        clips = sorted(q, key=lambda c: (c.speaker, c.sentence_id))
        if not clips:
            return _resp({"message": "No clips for that language/speaker."}, 404)

        name = f"dataset-{lang}" + (f"-{_slug(speaker)}" if speaker else "")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            meta = []
            for i, c in enumerate(clips, 1):
                cid = f"{i:04d}"
                src = os.path.join(storage.UPLOAD_DIR, c.filename)
                if not os.path.exists(src):
                    continue
                z.write(src, arcname=f"{name}/{cid}.wav")
                meta.append(f"{cid}|{c.transcript}")
            z.writestr(f"{name}/metadata.csv", "\n".join(meta) + "\n")
        buf.seek(0)
        return send_file(buf, mimetype="application/zip", as_attachment=True,
                         download_name=f"{name}.zip")
