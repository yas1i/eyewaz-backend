"""
Tests for the shared EYEWAZ voice registry.

Run:  python -m unittest discover -s tts-local -p 'test_*.py'

These lock down voice-id resolution, which several surfaces depend on: the web app
stores ids like "sh:urdu-female", the NVDA add-on and both TTS servers discover
voices from a folder, and older preferences still hold the language-only "sh:urdu".
"""

import json
import os
import tempfile
import unittest
from collections import OrderedDict

import voices as voicelib


def _registry(*ids):
    return OrderedDict(
        (vid, {"id": vid, "name": voicelib.pretty_name(vid),
               "gender": voicelib.gender_of(vid), "language": voicelib.language_of(vid),
               "sample_rate": 22050, "model": vid + ".onnx", "config": vid + ".onnx.json"})
        for vid in ids)


BOTH = _registry("eyewaz-urdu-female", "eyewaz-urdu-male")


class TestMetadata(unittest.TestCase):
    def test_gender_and_language_from_id(self):
        self.assertEqual(voicelib.gender_of("eyewaz-urdu-female"), "female")
        self.assertEqual(voicelib.gender_of("eyewaz-urdu-male"), "male")
        self.assertEqual(voicelib.gender_of("eyewaz-urdu"), "")
        self.assertEqual(voicelib.language_of("eyewaz-urdu-male"), "ur")
        self.assertEqual(voicelib.language_of("eyewaz-punjabi-male"), "pa")
        self.assertEqual(voicelib.language_of("eyewaz-sindhi-female"), "sd")

    def test_language_falls_back_to_urdu(self):
        # espeak-ng has no Saraiki; the plan is to speak it with the Urdu voice.
        self.assertEqual(voicelib.language_of("eyewaz-saraiki-male"), "ur")
        self.assertEqual(voicelib.language_of("mystery-voice"), "ur")

    def test_pretty_name_drops_product_prefix(self):
        self.assertEqual(voicelib.pretty_name("eyewaz-urdu-female"), "EYEWAZ Urdu (female)")


class TestResolve(unittest.TestCase):
    def test_canonical_and_alias(self):
        for requested in ("eyewaz-urdu-male", "urdu-male", "male", "sh:urdu-male",
                          "EYEWAZ-URDU-MALE", "  male  "):
            self.assertEqual(voicelib.resolve(requested, BOTH), "eyewaz-urdu-male",
                             f"failed for {requested!r}")

    def test_language_only_gives_that_languages_default(self):
        # Users who picked the self-hosted voice before it had per-gender ids have
        # "sh:urdu" stored; it must still speak, and with the female default.
        for requested in ("sh:urdu", "urdu", "ur"):
            self.assertEqual(voicelib.resolve(requested, BOTH), "eyewaz-urdu-female",
                             f"failed for {requested!r}")

    def test_unknown_and_empty_are_not_guessed(self):
        for requested in ("klingon", "sh:", "", None, "punjabi"):
            self.assertIsNone(voicelib.resolve(requested, BOTH), f"failed for {requested!r}")

    def test_ambiguous_alias_is_dropped(self):
        # Two Urdu female voices: "female" is ambiguous, so it must not resolve to
        # either one by accident. The full ids still work.
        two = _registry("eyewaz-urdu-female", "studio-urdu-female")
        self.assertIsNone(voicelib.resolve("female", two))
        self.assertEqual(voicelib.resolve("eyewaz-urdu-female", two), "eyewaz-urdu-female")

    def test_single_voice_still_answers_gender_and_language(self):
        one = _registry("eyewaz-urdu-male")
        self.assertEqual(voicelib.resolve("male", one), "eyewaz-urdu-male")
        self.assertEqual(voicelib.resolve("sh:urdu", one), "eyewaz-urdu-male")
        self.assertIsNone(voicelib.resolve("female", one))


class TestDefault(unittest.TestCase):
    def test_female_wins_regardless_of_order(self):
        self.assertEqual(voicelib.default_id(BOTH), "eyewaz-urdu-female")
        reversed_order = _registry("eyewaz-urdu-male", "eyewaz-urdu-female")
        self.assertEqual(voicelib.default_id(reversed_order), "eyewaz-urdu-female")

    def test_falls_back_to_first_when_no_female(self):
        self.assertEqual(voicelib.default_id(_registry("eyewaz-urdu-male")),
                         "eyewaz-urdu-male")
        self.assertIsNone(voicelib.default_id({}))


class TestDiscover(unittest.TestCase):
    def _voice_files(self, directory, vid, sample_rate=22050, with_config=True):
        open(os.path.join(directory, vid + ".onnx"), "wb").close()
        if with_config:
            with open(os.path.join(directory, vid + ".onnx.json"), "w") as fh:
                json.dump({"audio": {"sample_rate": sample_rate}}, fh)

    def test_finds_voices_and_reads_sample_rate(self):
        with tempfile.TemporaryDirectory() as d:
            self._voice_files(d, "eyewaz-urdu-female", sample_rate=22050)
            self._voice_files(d, "eyewaz-urdu-male", sample_rate=16000)
            found = voicelib.discover(d)
            self.assertEqual(sorted(found), ["eyewaz-urdu-female", "eyewaz-urdu-male"])
            self.assertEqual(found["eyewaz-urdu-male"]["sample_rate"], 16000)
            self.assertEqual(found["eyewaz-urdu-female"]["gender"], "female")

    def test_voice_without_config_is_skipped(self):
        # A model with no config would fail at synthesis time; better to not offer it.
        with tempfile.TemporaryDirectory() as d:
            self._voice_files(d, "eyewaz-urdu-male", with_config=False)
            self.assertEqual(voicelib.discover(d), {})

    def test_missing_directory_is_empty_not_an_error(self):
        self.assertEqual(voicelib.discover("/nonexistent/voices"), {})
        self.assertEqual(voicelib.discover(None), {})


if __name__ == "__main__":
    unittest.main()
