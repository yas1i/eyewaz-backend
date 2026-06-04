import requests, os, time
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("TRANSLATION_KEY")
region = os.getenv("REGION")
endpoint = os.getenv("TEXT_TRANSLATION_ENDPOINT")
COG_endpoint = os.getenv("DOCUMENT_TRANSLATION_ENDPOINT")

def get_text(image_url, computervision_client):
    # Open local image file
    read_response = computervision_client.read(image_url, raw=True)

    # Get the operation location (URL with an ID at the end)
    read_operation_location = read_response.headers["Operation-Location"]
    # Grab the ID from the URL
    operation_id = read_operation_location.split("/")[-1]

    # Retrieve the results 
    while True:
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status.lower() not in ["notstarted", "running"]:
            break
        time.sleep(1)

    # Get the detected text
    text = ""
    if read_result.status == OperationStatusCodes.succeeded:
        for page in read_result.analyze_result.read_results:
            for line in page.lines:
                # Get text in each detected line and do some fixes to the structure
                if (not text) or text[-1].strip() == "." or text[-1].strip() == ":":
                    text = text + "\n" + line.text
                else:
                    text = text + " " + line.text
    text = text.replace(" .", ".").replace(" ,", ",").replace(" :", ":")
    return text

def detect_language(text, key, region, endpoint):
    # Use the Translator detect function
    path = "/detect"
    url = endpoint + path
    # Build the request
    params = {
        "api-version": "3.0"
    }
    headers = {
    "Ocp-Apim-Subscription-Key": key,
    "Ocp-Apim-Subscription-Region": region,
    "Content-type": "application/json"
    }
    body = [{
        "text": text
    }]
    # Send the request and get response
    request = requests.post(url, params=params, headers=headers, json=body)
    response = request.json()
    # Get language
    language = response[0]["language"]
    # Return the language
    return language

def translate(text, source_language, target_language, key, region, endpoint):
    # Use the Translator translate function
    url = endpoint + "/translate"
    # Build the request
    params = {
        "api-version": "3.0",
        "from": source_language,
        "to": target_language
    }
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-type": "application/json"
    }
    body = [{
        "text": text
    }]
    # Send the request and get response
    request = requests.post(url, params=params, headers=headers, json=body)
    response = request.json()
    # Get translation
    translation = response[0]["translations"][0]["text"]
    # Return the translation
    return translation


def getTextfromImage():
    # Read the values from the form
    image_url = 'img/notes1.jpg'
    target_language = 'ur-PK'
    # Authenticate Computer Vision client
    computervision_client = ComputerVisionClient(COG_endpoint, CognitiveServicesCredentials(key))
    # Extract text
    text = get_text(image_url, computervision_client)
    # Detect language
    language = detect_language(text, key, region, endpoint)
    # Translate text
    translated_text = translate(text, language, target_language, key, region, endpoint)

    print("Original Text: ",text)
    print("Translated Text: ",translated_text)
    print("target_language: ",target_language)


def ConvertEnglishtoUrdu():
    lang = detect_language("How are you",key,region,endpoint)
    print("Detected Language:", lang)
    trans_lang=translate("Hey how are you doing?\r\nI am doing good.\r\nIs this a cat?\r\nMy name is Usman.",lang,'ur-PK',key,region,endpoint)
    print("Translation in Urdu Language:", trans_lang)
    #print ("".join(reversed(trans_lang)))

if __name__ == '__main__':
    ''' GET TEXT FROM IMAGE AND TRANSLATE BELOW'''
    #getTextfromImage()

    ''' CONVERT ENGLISH TO URDU'''
    ConvertEnglishtoUrdu()
    