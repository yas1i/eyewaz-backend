import os, requests, io
from flask import request, jsonify, Response
from flask_restful import Resource
from database.models import Docs, Users
import json

class PausePlaybackAPI(Resource):
    def put(self):
        """Updates last played time of document"""
        try:
            data = request.get_json(force=True)
            print(data)
            doc = Docs.objects.get(doc_name = data["doc_name"])
            doc.lastplayedtime = data["lastplayedtime"]
            doc.save()
            return Response(
                json.dumps({"message":"Last played time of " + doc.doc_name + " is "+doc.lastplayedtime+"."}),
                status=200,
                mimetype="application/json",
            )
        except:
            return jsonify(success=False)
    def post(self):
        '''BOOKMARKS THE DOCUMENT TO A TIME'''    
        try:
            data = request.get_json(force=True)
            print(data)
            doc = Docs.objects.get(doc_name = data["doc_name"])
            print(data)
            doc.bookmark = data["bookmark"]
            doc.save()
            return Response(
                json.dumps({"message": doc.doc_name + " is bookmarked at "+doc.bookmark+"."}),
                status=200,
                mimetype="application/json",
            )
        except:
            return jsonify(success=False)