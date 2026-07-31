"""
Tests for the self-hosted TTS client: which Urdu voice we pick, and what we
actually send to the engine.

Run:  python -m unittest test_selfhost_tts -v

These lock down the two things that broke silently before: the listener's
male/female choice never reaching the engine, and a one-off network blip
blanking the voice picker.
"""

import os
import unittest
from unittest import mock

import selfhost_tts


FEMALE = {"id": "eyewaz-urdu-female", "name": "EYEWAZ Urdu (female)",
          "gender": "female", "language": "ur", "sample_rate": 22050}
MALE = {"id": "eyewaz-urdu-male", "name": "EYEWAZ Urdu (male)",
        "gender": "male", "language": "ur", "sample_rate": 22050}


class _Resp:
    def __init__(self, payload=None, content=b"", status=200):
        self._payload, self.content, self.status = payload, content, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


class VoiceListTests(unittest.TestCase):
    def setUp(self):
        selfhost_tts._VOICES_CACHE = None
        self.env = mock.patch.dict(os.environ, {
            "SELF_HOST_TTS_URL": "https://tts.eyewaz.com",
            "SELF_HOST_TTS_KEY": "secret",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_no_url_means_no_voices(self):
        with mock.patch.dict(os.environ, {"SELF_HOST_TTS_URL": ""}):
            self.assertEqual(selfhost_tts.voices(), [])
            self.assertIsNone(selfhost_tts.default_voice())

    def test_sends_the_api_key(self):
        with mock.patch("selfhost_tts.requests.get",
                        return_value=_Resp([FEMALE, MALE])) as get:
            selfhost_tts.voices()
        self.assertEqual(get.call_args.kwargs["headers"]["X-API-Key"], "secret")

    def test_default_is_female(self):
        with mock.patch("selfhost_tts.requests.get", return_value=_Resp([MALE, FEMALE])):
            self.assertEqual(selfhost_tts.default_voice(), "sh:eyewaz-urdu-female")

    def test_default_falls_back_to_any_urdu_voice(self):
        with mock.patch("selfhost_tts.requests.get", return_value=_Resp([MALE])):
            self.assertEqual(selfhost_tts.default_voice(), "sh:eyewaz-urdu-male")

    def test_a_blip_keeps_the_last_good_list(self):
        with mock.patch("selfhost_tts.requests.get", return_value=_Resp([FEMALE, MALE])):
            self.assertEqual(len(selfhost_tts.voices()), 2)
        selfhost_tts._VOICES_CACHE = (0, [FEMALE, MALE])   # expire the TTL
        with mock.patch("selfhost_tts.requests.get", side_effect=OSError("network down")):
            self.assertEqual(len(selfhost_tts.voices()), 2)

    def test_failure_with_no_cache_is_empty_not_an_error(self):
        with mock.patch("selfhost_tts.requests.get", side_effect=OSError("network down")):
            self.assertEqual(selfhost_tts.voices(), [])

    def test_garbage_response_does_not_poison_the_cache(self):
        with mock.patch("selfhost_tts.requests.get", return_value=_Resp({"oops": 1})):
            self.assertEqual(selfhost_tts.voices(), [])
        self.assertIsNone(selfhost_tts._VOICES_CACHE)


class SynthTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {
            "SELF_HOST_TTS_URL": "https://tts.eyewaz.com",
            "SELF_HOST_TTS_KEY": "secret",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def _wav(self):
        import io
        import numpy as np
        import soundfile as sf
        buf = io.BytesIO()
        sf.write(buf, np.zeros(2205, dtype="float32"), 22050, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    def test_the_chosen_voice_reaches_the_engine(self):
        with mock.patch("selfhost_tts.requests.post",
                        return_value=_Resp(content=self._wav())) as post:
            selfhost_tts.synth("سلام", 1.0, voice="eyewaz-urdu-male")
        self.assertEqual(post.call_args.kwargs["json"]["voice"], "eyewaz-urdu-male")

    def test_no_voice_lets_the_engine_choose(self):
        with mock.patch("selfhost_tts.requests.post",
                        return_value=_Resp(content=self._wav())) as post:
            selfhost_tts.synth("سلام", 1.0)
        self.assertNotIn("voice", post.call_args.kwargs["json"])


if __name__ == "__main__":
    unittest.main()
