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

MAX_CLIP_BYTES = 20 * 1024 * 1024   # 20 MB per clip is plenty for one sentence

# Optional S3-compatible object storage (Backblaze B2 / Cloudflare R2) so the
# bank survives restarts on disk-less hosts like Render's free tier. Configured
# entirely via env: S3_BUCKET + S3_ENDPOINT + S3_ACCESS_KEY_ID +
# S3_SECRET_ACCESS_KEY (optional S3_REGION). Unset -> local filesystem.
_S3_CLIENT = None


def _s3():
    global _S3_CLIENT
    if not os.getenv("S3_BUCKET"):
        return None
    if _S3_CLIENT is None:
        import boto3
        _S3_CLIENT = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT"),
            region_name=os.getenv("S3_REGION") or None,
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        )
    return _S3_CLIENT


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-") or "anon"


def _resp(payload, status):
    return Response(json.dumps(payload), status=status, mimetype="application/json")


def _duration_bytes(data):
    try:
        import soundfile as sf
        info = sf.info(io.BytesIO(data))
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

        data = request.files["audio"].read()
        if not data:
            return _resp({"message": "Empty audio upload."}, 400)
        if len(data) > MAX_CLIP_BYTES:
            return _resp({"message": "Clip too large."}, 413)

        rel_path = f"voicebank/{lang}/{speaker}/{sentence_id}.wav"
        s3 = _s3()
        if s3:
            s3.put_object(Bucket=os.getenv("S3_BUCKET"), Key=rel_path,
                          Body=data, ContentType="audio/wav")
        else:
            abs_path = os.path.join(storage.UPLOAD_DIR, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as fh:
                fh.write(data)

        dur = _duration_bytes(data)
        # One clip per (lang, speaker, sentence_id): re-recording replaces it.
        VoiceClip.objects(lang=lang, speaker=speaker, sentence_id=sentence_id).delete()
        VoiceClip(
            lang=lang, speaker=speaker, gender=gender, sentence_id=sentence_id,
            transcript=transcript, filename=rel_path,
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
        s3 = _s3()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            meta = []
            for i, c in enumerate(clips, 1):
                cid = f"{i:04d}"
                if s3:
                    try:
                        body = s3.get_object(Bucket=os.getenv("S3_BUCKET"),
                                             Key=c.filename)["Body"].read()
                    except Exception:
                        continue
                    z.writestr(f"{name}/{cid}.wav", body)
                else:
                    src = os.path.join(storage.UPLOAD_DIR, c.filename)
                    if not os.path.exists(src):
                        continue
                    z.write(src, arcname=f"{name}/{cid}.wav")
                meta.append(f"{cid}|{c.transcript}")
            z.writestr(f"{name}/metadata.csv", "\n".join(meta) + "\n")
        buf.seek(0)
        return send_file(buf, mimetype="application/zip", as_attachment=True,
                         download_name=f"{name}.zip")
