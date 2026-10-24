"""
Urdu is spoken by our own voice on every route that speaks, never Azure, unless
our engine fails. Azure, the engine and storage are all mocked.

Run:  python -m unittest test_voice_routing -v

Locks down the October leak: the screen reader and document reading sent saved
Azure Urdu names ("ur-PK-UzmaNeural", the old default everywhere) straight to
Azure, so Urdu kept costing money after our own voice went live.
"""

import os
import unittest
from unittest import mock

from flask_jwt_extended import create_access_token

import selfhost_tts
from resources import documents, web
from server import app


FEMALE = {"id": "eyewaz-urdu-female", "gender": "female", "language": "ur"}
MALE = {"id": "eyewaz-urdu-male", "gender": "male", "language": "ur"}


class _Stored:
    url = "https://example.invalid/audio"
    blob_name = "doc_audio.wav"


class _EngineUp(unittest.TestCase):
    """Our engine configured and listing both Urdu voices; Azure recorded, not called."""

    def setUp(self):
        selfhost_tts._VOICES_CACHE = None
        patches = [
            mock.patch.dict(os.environ, {"SELF_HOST_TTS_URL": "https://tts.example.invalid"}),
            mock.patch.object(selfhost_tts, "voices", return_value=[FEMALE, MALE]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.ours = mock.patch.object(selfhost_tts, "synth", return_value=b"RIFFours").start()
        self.addCleanup(mock.patch.stopall)


class RemapTests(_EngineUp):
    def test_azure_urdu_female_becomes_ours(self):
        self.assertEqual(web.ours_for_azure_urdu("ur-PK-UzmaNeural"), "sh:eyewaz-urdu-female")

    def test_azure_urdu_male_keeps_gender(self):
        self.assertEqual(web.ours_for_azure_urdu("ur-PK-AsadNeural"), "sh:eyewaz-urdu-male")

    def test_other_languages_untouched(self):
        for v in ("pa-IN-VaaniNeural", "ps-AF-LatifaNeural", "sh:urdu-male", "el:abc"):
            self.assertEqual(web.ours_for_azure_urdu(v), v)

    def test_engine_off_keeps_azure_so_urdu_still_speaks(self):
        with mock.patch.dict(os.environ, {"SELF_HOST_TTS_URL": ""}):
            self.assertEqual(web.ours_for_azure_urdu("ur-PK-UzmaNeural"), "ur-PK-UzmaNeural")


class ScreenReaderTests(_EngineUp):
    def setUp(self):
        super().setUp()
        self.azure = mock.patch.object(web, "synthesize").start()
        self.azure.return_value.audio_data = b"ID3azure"
        mock.patch.object(web, "translate", side_effect=lambda t, a, b: "اردو متن").start()
        mock.patch.object(web.storage, "save_file", return_value=_Stored()).start()
        with app.app_context():
            tok = create_access_token(identity="voice-test@example.com")
        self.h = {"Authorization": "Bearer " + tok}
        self.c = app.test_client()

    def _read(self, voice):
        return self.c.post("/api/screen-reader", headers=self.h,
                           json={"text": "Settings", "voice": voice})

    def test_android_default_azure_name_uses_our_voice(self):
        r = self._read("ur-PK-UzmaNeural")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ours.call_args.kwargs["voice"], "eyewaz-urdu-female")
        self.azure.assert_not_called()

    def test_male_choice_reaches_our_male_voice(self):
        self._read("ur-PK-AsadNeural")
        self.assertEqual(self.ours.call_args.kwargs["voice"], "eyewaz-urdu-male")
        self.azure.assert_not_called()

    def test_new_android_default_uses_our_voice(self):
        self._read("sh:urdu-female")
        self.assertEqual(self.ours.call_args.kwargs["voice"], "urdu-female")
        self.azure.assert_not_called()

    def test_engine_failure_still_speaks_via_azure(self):
        self.ours.side_effect = RuntimeError("engine down")
        r = self._read("ur-PK-AsadNeural")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.azure.call_args.args[1], "ur-PK-AsadNeural")


class DocumentTests(_EngineUp):
    def setUp(self):
        super().setUp()
        self.azure = mock.patch.object(documents, "synthesize_long",
                                       return_value=b"ID3azure").start()
        mock.patch.object(documents, "ConvertText", return_value=("اردو متن", "en")).start()
        mock.patch.object(documents, "get_audio_duration_from_bytes", return_value=3).start()
        self.uploads = []

        def upload(data, name):
            self.uploads.append(name)
            blob = mock.Mock(blob_name=name, url="https://example.invalid/" + name)
            blob.read_bytes.return_value = b"Hello world"
            return blob
        mock.patch.object(documents, "UploadOnAzure", side_effect=upload).start()

    def _doc(self, voice):
        return documents.translationSpeechTask(mock.Mock(filename="note.txt"), "ur-PK", voice)

    def test_saved_azure_default_uses_our_voice(self):
        self._doc("ur-PK-UzmaNeural")
        self.assertEqual(self.ours.call_args.kwargs["voice"], "eyewaz-urdu-female")
        self.azure.assert_not_called()
        self.assertTrue(self.uploads[-1].endswith(".wav"))

    def test_chosen_our_voice_reaches_the_engine(self):
        self._doc("sh:eyewaz-urdu-male")
        self.assertEqual(self.ours.call_args.kwargs["voice"], "eyewaz-urdu-male")
        self.azure.assert_not_called()

    def test_engine_failure_falls_back_to_azure_as_mp3(self):
        self.ours.side_effect = RuntimeError("engine down")
        self._doc("ur-PK-AsadNeural")
        self.assertEqual(self.azure.call_args.args[1], "ur-PK-AsadNeural")
        self.assertTrue(self.uploads[-1].endswith(".mp3"))

    def test_clone_without_elevenlabs_uses_our_voice(self):
        with mock.patch("elevenlabs_api.configured", return_value=False):
            self._doc("el:abc")
        self.ours.assert_called_once()
        self.azure.assert_not_called()

    def test_punjabi_stays_on_azure(self):
        self._doc("pa-IN-VaaniNeural")
        self.ours.assert_not_called()
        self.assertEqual(self.azure.call_args.args[1], "pa-IN-VaaniNeural")


class DialectFallbackTests(_EngineUp):
    """Dialects with no voice of their own (Sindhi, Saraiki...) fall back to Urdu."""

    def _fallbacks(self):
        from resources import dialects
        with mock.patch.object(dialects, "list_voices", return_value=[]), \
                mock.patch.object(dialects.DialectVoice, "objects", return_value=[]):
            dialects._VOICE_CACHE = None
            with app.app_context():
                tok = create_access_token(identity="voice-test@example.com")
            r = app.test_client().get("/api/dialects",
                                      headers={"Authorization": "Bearer " + tok})
        return {d["fallback_voice"] for d in r.get_json()["dialects"]}

    def test_fallback_is_our_voice(self):
        self.assertEqual(self._fallbacks(), {"sh:eyewaz-urdu-female"})

    def test_fallback_is_azure_when_engine_off(self):
        with mock.patch.object(selfhost_tts, "voices", return_value=[]):
            self.assertEqual(self._fallbacks(), {"ur-PK-UzmaNeural"})


PUNJABI = {"id": "eyewaz-punjabi-male", "gender": "male", "language": "pa"}


class PunjabiTests(_EngineUp):
    """Our trained Punjabi voice replaces Azure for the Punjabi dialect, and only there."""

    def setUp(self):
        super().setUp()
        mock.patch.object(selfhost_tts, "voices", return_value=[FEMALE, MALE, PUNJABI]).start()

    def _dialects(self):
        from resources import dialects
        with mock.patch.object(dialects, "list_voices",
                               return_value=[{"shortName": "pa-IN-VaaniNeural", "gender": "Female"}]), \
                mock.patch.object(dialects.DialectVoice, "objects", return_value=[]):
            dialects._VOICE_CACHE = None
            with app.app_context():
                tok = create_access_token(identity="voice-test@example.com")
            r = app.test_client().get("/api/dialects",
                                      headers={"Authorization": "Bearer " + tok})
        return {d["id"]: d for d in r.get_json()["dialects"]}

    def test_punjabi_dialect_uses_our_voice_and_urdu_script(self):
        pa = self._dialects()["punjabi"]
        self.assertEqual([v["shortName"] for v in pa["voices"]], ["sh:eyewaz-punjabi-male"])
        self.assertEqual(pa["locale"], "ur-PK")   # Shahmukhi, never Azure's Gurmukhi
        self.assertEqual(pa["tier"], "free")

    def test_urdu_does_not_list_the_punjabi_voice(self):
        ur = self._dialects()["urdu"]
        self.assertEqual({v["shortName"] for v in ur["voices"]},
                         {"sh:eyewaz-urdu-female", "sh:eyewaz-urdu-male"})

    def test_urdu_default_stays_urdu(self):
        self.assertEqual(selfhost_tts.default_voice(), "sh:eyewaz-urdu-female")

    def test_punjabi_falls_back_to_azure_without_our_voice(self):
        mock.patch.object(selfhost_tts, "voices", return_value=[FEMALE, MALE]).start()
        pa = self._dialects()["punjabi"]
        self.assertEqual(pa["voices"][0]["shortName"], "pa-IN-VaaniNeural")
        self.assertEqual(pa["locale"], "pa-IN")

    def test_punjabi_speech_reaches_the_engine(self):
        mock.patch.object(web, "synthesize").start()
        mock.patch.object(web, "translate", side_effect=lambda t, a, b: "اردو متن").start()
        mock.patch.object(web.storage, "save_file", return_value=_Stored()).start()
        with app.app_context():
            tok = create_access_token(identity="voice-test@example.com")
        r = app.test_client().post("/api/screen-reader", headers={"Authorization": "Bearer " + tok},
                                   json={"text": "Settings", "voice": "sh:eyewaz-punjabi-male"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ours.call_args.kwargs["voice"], "eyewaz-punjabi-male")


if __name__ == "__main__":
    unittest.main()
