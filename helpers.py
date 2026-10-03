import random
import string
import io
import requests, os, time
import hashlib
import re
from datetime import datetime
import storage
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# Load .env from this file's directory (cwd-independent).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

key = os.getenv("TRANSLATION_KEY")
region = os.getenv("REGION")
endpoint = os.getenv("TEXT_TRANSLATION_ENDPOINT")
COG_endpoint = os.getenv("DOCUMENT_TRANSLATION_ENDPOINT")
connect_str = os.getenv("AZURE_CONNECTION_STRING")
container_str = os.getenv("AZURE_CONTAINER")
vision_key = os.getenv("VISION_KEY")
vision_endpoint = os.getenv("VISION_ENDPOINT")


def id_generator(size=32, chars=string.ascii_uppercase + string.digits):
    return "".join(random.choice(chars) for _ in range(size))


def detect_language(text):
    # Use the Translator detect function
    path = "/detect"
    url = os.getenv("TEXT_TRANSLATION_ENDPOINT") + path
    # Build the request
    params = {"api-version": "3.0"}
    headers = {
        "Ocp-Apim-Subscription-Key": os.getenv("TRANSLATION_KEY"),
        "Ocp-Apim-Subscription-Region": os.getenv("REGION"),
        "Content-type": "application/json",
    }
    body = [{"text": text}]
    # Send the request and get response
    request = requests.post(url, params=params, headers=headers, json=body)
    response = request.json()
    # Get language
    language = response[0]["language"]
    # Return the language
    return language


# Characters only Urdu uses (not Arabic or Persian). Text in Arabic script that
# contains one of these is already Urdu, so translating it into Urdu is paid-for
# work that returns the same words.
_URDU_ONLY = re.compile("[\u0679\u0688\u0691\u06BA\u06D2\u06D3\u06BE\u06D4]")
_ARABIC_SCRIPT = re.compile("[\u0600-\u06FF\u0750-\u077F]")
_LATIN = re.compile("[A-Za-z]")
_LETTER = re.compile(r"[^\W\d_]")


def looks_urdu(text):
    """True when text is mostly Arabic script and carries Urdu-only letters."""
    a = len(_ARABIC_SCRIPT.findall(text))
    l = len(_LATIN.findall(text))
    return a > 0 and a >= 0.6 * (a + l) and bool(_URDU_ONLY.search(text))


def _cache_key(src, tgt, text):
    return hashlib.sha256(f"{src or 'auto'}|{tgt}|{text}".encode("utf-8")).hexdigest()


def _cache_get(k):
    try:
        from database.models import TranslationCache
        row = TranslationCache.objects(key=k).first()
        return (row.translated, row.detected) if row else None
    except Exception as e:  # the cache must never break a translation
        print(f"translation cache read skipped: {e}", flush=True)
        return None


def _cache_put(k, translated, detected):
    try:
        from database.models import TranslationCache
        TranslationCache.objects(key=k).update_one(
            set__translated=translated, set__detected=detected or "",
            set_on_insert__created_at=datetime.utcnow(), upsert=True)
    except Exception as e:
        print(f"translation cache write skipped: {e}", flush=True)


def translate_detect(text, target_language="ur-PK", source_language=None):
    """Translate text and return (translation, detected_source).

    Cost rules, because Azure Translator bills every character sent:
    - no letters (numbers, punctuation) or already-Urdu text going to Urdu is
      returned as is, without a call;
    - repeats come from the TranslationCache;
    - with no source_language, Azure detects the language inside the same
      translate call, so we never pay a separate /detect on the same text.
    """
    tgt_base = target_language.split("-")[0]
    if not text or not _LETTER.search(text):
        return text, source_language or ""
    if tgt_base == "ur" and looks_urdu(text):
        return text, "ur"

    k = _cache_key(source_language, target_language, text)
    hit = _cache_get(k)
    if hit:
        return hit

    url = os.getenv("TEXT_TRANSLATION_ENDPOINT") + "/translate"
    params = {"api-version": "3.0", "to": target_language}
    if source_language:
        params["from"] = source_language
    headers = {
        "Ocp-Apim-Subscription-Key": os.getenv("TRANSLATION_KEY"),
        "Ocp-Apim-Subscription-Region": os.getenv("REGION"),
        "Content-type": "application/json",
    }
    response = requests.post(url, params=params, headers=headers, json=[{"text": text}]).json()
    item = response[0]
    translated = item["translations"][0]["text"]
    detected = source_language or (item.get("detectedLanguage") or {}).get("language", "")
    _cache_put(k, translated, detected)
    return translated, detected


def translate(text, source_language, target_language="ur-PK"):
    return translate_detect(text, target_language, source_language)[0]


def ConvertEnglishtoUrdu(text):
    trans_lang, lang = translate_detect(text, "ur-PK")
    print("Detected Language:", lang)
    return trans_lang, lang


def ConvertText(text, target_lang="ur-PK"):
    """Translate text into target_lang. Returns (translated_text, source_lang).
    If the text is already in the target language, returns it unchanged."""
    translated, src = translate_detect(text, target_lang)
    print(f"Detected source: {src} -> target: {target_lang}")
    if src == target_lang.split("-")[0]:
        return text, src
    return translated, src


# This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"


def TexttoSpeech_Female(text):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("SPEECH_KEY"), region=os.getenv("REGION")
        )

        # audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
        output_file = "test_output.mp3"
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
        # The language of the voice that speaks.
        speech_config.speech_synthesis_voice_name = "ur-PK-UzmaNeural"
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_SynthOutputFormat,
            "audio-48khz-192kbitrate-mono-mp3",
        )

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
        if (
            speech_synthesis_result.reason
            == speechsdk.ResultReason.SynthesizingAudioCompleted
        ):
            print("Speech synthesized for text [{}]".format(text))
        elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_synthesis_result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    print(
                        "Error details: {}".format(cancellation_details.error_details)
                    )
                    print("Did you set the speech resource key and region values?")
        return speech_synthesis_result
    except Exception as e:
        # Surface the real failure instead of masking it (str(e), not e.message,
        # which is a Python-2 idiom that raises AttributeError on Python 3).
        print(f"Text-to-speech failed: {e}")
        raise
        
def TexttoSpeech_Male(text):
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("SPEECH_KEY"), region=os.getenv("REGION")
        )

        # audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=False)
        output_file = "test_output.mp3"
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
        # The language of the voice that speaks.
        speech_config.speech_synthesis_voice_name = "ur-PK-AsadNeural"
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_SynthOutputFormat,
            "audio-48khz-192kbitrate-mono-mp3",
        )

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()
        if (
            speech_synthesis_result.reason
            == speechsdk.ResultReason.SynthesizingAudioCompleted
        ):
            print("Speech synthesized for text [{}]".format(text))
        elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_synthesis_result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    print(
                        "Error details: {}".format(cancellation_details.error_details)
                    )
                    print("Did you set the speech resource key and region values?")
        return speech_synthesis_result
    except Exception as e:
        # Surface the real failure instead of masking it (str(e), not e.message,
        # which is a Python-2 idiom that raises AttributeError on Python 3).
        print(f"Text-to-speech failed: {e}")
        raise


def _speech_config():
    cfg = speechsdk.SpeechConfig(subscription=os.getenv("SPEECH_KEY"), region=os.getenv("REGION"))
    cfg.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_SynthOutputFormat,
        "audio-48khz-192kbitrate-mono-mp3",
    )
    return cfg


def list_voices():
    """Return Azure's full catalogue of neural voices (all languages)."""
    region = os.getenv("REGION")
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    r = requests.get(url, headers={"Ocp-Apim-Subscription-Key": os.getenv("SPEECH_KEY")}, timeout=20)
    r.raise_for_status()
    return [
        {
            "shortName": v["ShortName"],
            "locale": v["Locale"],
            "localeName": v.get("LocaleName", v["Locale"]),
            "displayName": v.get("LocalName") or v.get("DisplayName", v["ShortName"]),
            "gender": v.get("Gender", ""),
        }
        for v in r.json()
        if v.get("VoiceType") == "Neural" or "Neural" in v.get("ShortName", "")
    ]


def synthesize(text, voice_name, rate=1.0):
    """Synthesize text with any Azure voice and speaking rate (returns result)."""
    cfg = _speech_config()
    cfg.speech_synthesis_voice_name = voice_name
    synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        rate = 1.0
    if abs(rate - 1.0) < 0.01:
        return synth.speak_text_async(text).get()
    # Use SSML to control rate (as a multiplier of the default speaking rate).
    locale = "-".join(voice_name.split("-")[:2]) if "-" in voice_name else "en-US"
    escaped = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ssml = (
        f"<speak version='1.0' xml:lang='{locale}'>"
        f"<voice name='{voice_name}'><prosody rate='{rate:.2f}'>{escaped}</prosody></voice></speak>"
    )
    return synth.speak_ssml_async(ssml).get()


def synthesize_long(text, voice_name, rate=1.0, max_chunk=2500):
    """Synthesize long text by chunking on word boundaries and concatenating the
    MP3 output, so documents/books don't exceed a single TTS request's limits.
    Returns raw audio bytes."""
    words = (text or "").split(" ")
    chunks, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chunk:
            if cur:
                chunks.append(cur)
            cur = w
        else:
            cur = (cur + " " + w) if cur else w
    if cur:
        chunks.append(cur)
    audio = b""
    for c in chunks:
        audio += synthesize(c, voice_name, rate).audio_data
    return audio


def UploadOnAzure(file, filename):
    """Store a file and return a blob-like handle.

    Storage moved from Azure Blob to the local filesystem (see storage.py);
    the name is kept so call sites stay unchanged.
    """
    return storage.save_file(file, filename)


def ImagetoText(image):
    """OCR an image to text using Azure Vision's Read API.

    ``image`` is the raw image bytes (or a file-like object). We send the bytes
    directly via ``read_in_stream`` rather than a URL, because images are now
    stored locally and Azure's cloud service cannot reach a localhost URL.
    """
    print("===== Read File - stream =====")
    computervision_client = ComputerVisionClient(
        vision_endpoint, CognitiveServicesCredentials(vision_key)
    )

    if isinstance(image, (bytes, bytearray)):
        stream = io.BytesIO(bytes(image))
    else:
        stream = image

    # Call API with the image stream and raw response (to read the op location)
    read_response = computervision_client.read_in_stream(stream, raw=True)

    # Get the operation location (URL with an ID at the end) from the response
    read_operation_location = read_response.headers["Operation-Location"]
    # Grab the ID from the URL
    operation_id = read_operation_location.split("/")[-1]

    # Call the "GET" API and wait for it to retrieve the results
    while True:
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status not in ["notStarted", "running"]:
            break
        time.sleep(1)
    returnsString = ""
    # Print the detected text, line by line
    if read_result.status == OperationStatusCodes.succeeded:
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                returnsString = returnsString + line.text
                # print(line.text)
                # print(line.bounding_box)
            print(returnsString)
    return returnsString
