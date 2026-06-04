from flask import Response, request, jsonify
import json
from flask_restful import Resource
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials

import os
import time

from database.models import Users, Images
from helpers import UploadOnAzure, ImagetoText, ConvertEnglishtoUrdu, TexttoSpeech

'''
Authenticate
Authenticates your credentials and creates a client.
'''
""" vision_key = "190b36a9358d4ae4addb1466cae09940"
vision_endpoint = "https://eyewaz-vision.cognitiveservices.azure.com/" """


'''
END - Authenticate
'''

class ImageText(Resource):
    
    def post(self):
        email = request.form["email"]
        print(email)
        user = Users.objects.get(email=email)
        i = request.files["image"]
        blob_client = UploadOnAzure(i, i.filename)
        print(blob_client.url, blob_client.blob_name)
        visiontext = ImagetoText(blob_client.url)
        print(visiontext)
        Trans_text, lang = ConvertEnglishtoUrdu(visiontext)
        
        audio = TexttoSpeech(Trans_text)
        audio_data = audio.audio_data
        # Generate a unique filename
        audio_filename = blob_client.blob_name.split('.')[0] + '.wav'
        audio_blob_client = UploadOnAzure(audio_data, audio_filename)
        
        data = {
            "img_url":blob_client.url,
            "img_name":blob_client.blob_name,
            "img_extension":blob_client.blob_name.split('.')[-1],
            "eng_text":visiontext,
            "tran_text":Trans_text,
            "lang":lang,
            "trans_lang":"ur-PK",
            "audio_url":audio_blob_client.url,
            "audio_name":audio_blob_client.blob_name,
            "audio_extension":audio_blob_client.blob_name.split('.')[-1],
            "message":blob_client.blob_name + " Is Uploaded"
        }
        
        img = Images(user = user, img_url=data["img_url"],
                     img_name=data["img_name"],
                     img_extension=data["img_extension"],
                     raw_text=data["eng_text"],
                     trans_text=data["tran_text"],
                     lang=data["lang"],
                     trans_lang=data["trans_lang"],
                     audio_url=data["audio_url"],
                     audio_name=data["audio_name"],
                     audio_extension=data["audio_extension"]
                     ).save()
        
        return Response(img.to_json(), status = 200, mimetype='application/json')
    
    