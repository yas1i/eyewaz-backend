"""Translator cost guards: no paid call for Urdu-to-Urdu, empty text or repeats,
and language detection rides inside the single translate call. Azure is mocked."""
import os
import unittest
from unittest import mock

os.environ.setdefault("TEXT_TRANSLATION_ENDPOINT", "https://example.invalid")
import helpers


class FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class TranslateCostTests(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.calls = []
        p1 = mock.patch.object(helpers, "_cache_get", side_effect=lambda k: self.store.get(k))
        p2 = mock.patch.object(helpers, "_cache_put",
                               side_effect=lambda k, t, d: self.store.__setitem__(k, (t, d)))
        p3 = mock.patch.object(helpers.requests, "post", side_effect=self._post)
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)

    def _post(self, url, params=None, headers=None, json=None):
        self.calls.append((url, dict(params)))
        return FakeResp([{"detectedLanguage": {"language": "en", "score": 1.0},
                          "translations": [{"text": "ترجمہ", "to": "ur"}]}])

    def test_urdu_to_urdu_is_free(self):
        out = helpers.translate("آج موسم بہت اچھا ہے۔", "en", "ur")
        self.assertEqual(out, "آج موسم بہت اچھا ہے۔")
        self.assertEqual(self.calls, [])

    def test_arabic_is_still_translated(self):
        helpers.translate("السلام عليكم ورحمة الله", "ar", "ur")
        self.assertEqual(len(self.calls), 1)

    def test_numbers_only_is_free(self):
        self.assertEqual(helpers.translate("12:45 / 3.5%", "en", "ur"), "12:45 / 3.5%")
        self.assertEqual(self.calls, [])

    def test_repeat_hits_cache(self):
        a = helpers.translate("Battery low", "en", "ur")
        b = helpers.translate("Battery low", "en", "ur")
        self.assertEqual((a, b), ("ترجمہ", "ترجمہ"))
        self.assertEqual(len(self.calls), 1)

    def test_detect_rides_inside_one_call(self):
        out, lang = helpers.ConvertEnglishtoUrdu("Hello world")
        self.assertEqual((out, lang), ("ترجمہ", "en"))
        self.assertEqual(len(self.calls), 1)
        url, params = self.calls[0]
        self.assertTrue(url.endswith("/translate"))
        self.assertNotIn("from", params)

    def test_convert_text_same_language_returns_original(self):
        out, lang = helpers.ConvertText("Hello world", "en")
        self.assertEqual((out, lang), ("Hello world", "en"))

    def test_cache_failure_never_breaks_translation(self):
        with mock.patch.object(helpers, "_cache_get", side_effect=lambda k: None), \
             mock.patch.object(helpers, "_cache_put", side_effect=lambda *a: None):
            self.assertEqual(helpers.translate("Open", "en", "ur"), "ترجمہ")

    def test_real_cache_functions_swallow_db_errors(self):
        mock.patch.stopall()
        with mock.patch("database.models.TranslationCache.objects", side_effect=RuntimeError("no db")):
            self.assertIsNone(helpers._cache_get("k"))
            helpers._cache_put("k", "t", "en")  # must not raise


if __name__ == "__main__":
    unittest.main()
