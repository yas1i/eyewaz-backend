import random
import string
import io
import requests, os, time
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


def translate(text, source_language, target_language="ur-PK"):
    # Use the Translator translate function
    url = os.getenv("TEXT_TRANSLATION_ENDPOINT") + "/translate"
    # Build the request
    params = {"api-version": "3.0", "from": source_language, "to": target_language}
    headers = {
        "Ocp-Apim-Subscription-Key": os.getenv("TRANSLATION_KEY"),
        "Ocp-Apim-Subscription-Region": os.getenv("REGION"),
        "Content-type": "application/json",
    }
    body = [{"text": text}]
    # Send the request and get response
    request = requests.post(url, params=params, headers=headers, json=body)
    response = request.json()
    # Get translation
    translation = response[0]["translations"][0]["text"]
    # Return the translation
    return translation


def ConvertEnglishtoUrdu(text):
    lang = detect_language(text)
    print("Detected Language:", lang)
    trans_lang = translate(text, lang, "ur-PK")
    print("Translation in Urdu Language:", trans_lang)
    return trans_lang, lang


def ConvertText(text, target_lang="ur-PK"):
    """Translate text into target_lang. Returns (translated_text, source_lang).
    If the text is already in the target language, returns it unchanged."""
    src = detect_language(text)
    print(f"Detected source: {src} -> target: {target_lang}")
    if src == target_lang.split("-")[0]:
        return text, src
    return translate(text, src, target_lang), src


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
