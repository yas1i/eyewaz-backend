from flask import Response, request, jsonify
import json
from flask_restful import Resource
import uuid
import boto3
import json
import base64
import os
from dotenv import load_dotenv,find_dotenv
load_dotenv(find_dotenv())

'''
https://github.com/codesagar/Azure-Blobs/blob/master/blob.py
https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python?tabs=managed-identity%2Croles-azure-portal%2Csign-in-azure-cli
'''
class SpeechAPI(Resource):
    def post(self):
        '''
        Upload text to convert to urdu and save speech in azure
        '''
        data = request.get_json(force=True)
      
        resp=Response()
        resp.content_type = 'application/json'
        resp.set_data(json.dumps({'message':"Speech has been saved for uploaded file"}))
        return resp
    def get(self):
        '''
        Fetch the speech against the document
        '''