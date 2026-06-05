import io, requests
import os
import tempfile
import storage
from bs4 import BeautifulSoup
from helpers import ConvertText, synthesize, synthesize_long, UploadOnAzure, ImagetoText
from azure.storage.blob import BlobServiceClient, ContainerClient
from flask import request, jsonify, Response
from flask_restful import Resource
from database.models import Docs, Users, Folders
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
import soundfile as sf
import docx2txt
import shutil
import PyPDF2
import uuid

connect_str = os.getenv("AZURE_CONNECTION_STRING")
container_str = os.getenv("AZURE_CONTAINER")


def get_audio_duration_from_bytes(audio_bytes):
    audio_file = io.BytesIO(audio_bytes)
    data, samplerate = sf.read(audio_file)

    duration = len(data) / samplerate
    return duration

DOC_MAX_CHARS = 8000  # cap long documents/books so translate+TTS stay bounded


def _extract_epub(raw):
    """Extract readable text from an EPUB (a zip of (x)html chapters)."""
    import zipfile
    parts = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in sorted(z.namelist()):
            if name.lower().endswith((".xhtml", ".html", ".htm")):
                soup = BeautifulSoup(z.read(name), "html.parser")
                for t in soup(["script", "style"]):
                    t.decompose()
                parts.append(soup.get_text(" "))
    return "\n".join(parts)


def translationSpeechTask(f, target_lang="ur-PK", voice="ur-PK-UzmaNeural", rate=1.0):
    blob_client = UploadOnAzure(f, f.filename)
    raw = blob_client.read_bytes()
    ext = blob_client.blob_name.split(".")[-1].lower()
    text = ""

    if ext == "txt":
        text = raw.decode("utf-8", errors="ignore")
    elif ext == "pdf":
        reader = PyPDF2.PdfReader(io.BytesIO(raw))
        text = "".join((page.extract_text() or "") for page in reader.pages)
    elif ext in ("docx", "doc"):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            text = docx2txt.process(tmp_path)
        finally:
            os.unlink(tmp_path)
    elif ext == "epub":
        text = _extract_epub(raw)
    elif ext in ("png", "jpg", "jpeg"):
        # Send raw image bytes to Azure Vision (local files aren't a public URL).
        text = ImagetoText(raw)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    if not text or not text.strip():
        raise ValueError("No readable text was found in this file.")

    text = text[:DOC_MAX_CHARS]  # bound very long books

    # Translate into the user's chosen language and speak with their chosen voice.
    Trans_text, lang = ConvertText(text, target_lang)
    audio_data = synthesize_long(Trans_text, voice, rate)
    audio_duration = get_audio_duration_from_bytes(audio_data)
    audio_filename = blob_client.blob_name.split(".")[0] + "_audio.mp3"
    audio_blob_client = UploadOnAzure(audio_data, audio_filename)
    return text, Trans_text, lang, audio_duration, blob_client, audio_blob_client

class DocumentTransSpeechAPI(Resource):
    """Uploads file to Azure Blob Storage"""

    @jwt_required()
    def post(self):
        """
        Translates & Generates Speech for docs, pdfs, jpg, pngs for a user
        """
        if "file" not in request.files:
            return Response(json.dumps({"message": "No file was uploaded."}),
                            status=400, mimetype="application/json")
        f = request.files["file"]
        email = get_jwt_identity()
        user = Users.objects.get(email=email)
        prefs = user.preferences()
        target_lang = prefs.get("language", "ur-PK")
        voice = prefs.get("voice", "ur-PK-UzmaNeural")
        rate = prefs.get("rate", 1.0)

        try:
            text, Trans_text, lang, audio_duration, blob_client, audio_blob_client = \
                translationSpeechTask(f, target_lang, voice, rate)
        except ValueError as e:
            # Expected, user-facing problems (no text found, unsupported type).
            return Response(json.dumps({"message": str(e)}),
                            status=422, mimetype="application/json")
        except Exception as e:
            import traceback; traceback.print_exc()
            return Response(json.dumps({"message": f"Could not process the file: {e}"}),
                            status=500, mimetype="application/json")
        # A single audio in the user's chosen voice; stored in both audio fields
        # so the existing client (and library) keep working.
        data = {
            "doc_url": blob_client.url,
            "doc_name": blob_client.blob_name,
            "doc_extension": blob_client.blob_name.split(".")[-1],
            "eng_text": text,
            "tran_text": Trans_text,
            "lang": lang,
            "trans_lang": target_lang,
            "female_audio_url": audio_blob_client.url,
            "female_audio_name": audio_blob_client.blob_name,
            "female_audio_extension": audio_blob_client.blob_name.split(".")[-1],
            "female_audio_duration": audio_duration,
            "male_audio_url": audio_blob_client.url,
            "male_audio_name": audio_blob_client.blob_name,
            "male_audio_extension": audio_blob_client.blob_name.split(".")[-1],
            "male_audio_duration": audio_duration,
            "message": blob_client.blob_name + " Is Uploaded",
        }
        female_audio_duration = audio_duration
        male_audio_duration = audio_duration
        doc = Docs(
            id=str(uuid.uuid4()),
            user=user,
            doc_url=data["doc_url"],
            doc_name=data["doc_name"],
            doc_extension=data["doc_extension"],
            eng_text=data["eng_text"],
            trans_text=data["tran_text"],
            lang=data["lang"],
            trans_lang=data["trans_lang"],
            female_audio_url=data["female_audio_url"],
            female_audio_name=data["female_audio_name"],
            female_audio_extension=data["female_audio_extension"],
            female_audio_duration=female_audio_duration,
            male_audio_url=data["male_audio_url"],
            male_audio_name=data["male_audio_name"],
            male_audio_extension=data["male_audio_extension"],
            male_audio_duration=male_audio_duration,
            fav=False
        ).save()

        return Response(doc.to_json(), status=200, mimetype="application/json")
        # except Exception as e:
        #    return Response(status=400, mimetype='application/json')
        # return jsonify(success=False)

    @jwt_required()
    def get(self):
        """
        Lists all documents for a user
        """
        email = get_jwt_identity()
        user = Users.objects.get(email=email)
        userDocs = Docs.objects(user=user)
        myFiles = []
        for docs in userDocs:
            myFiles.append(json.loads(docs.to_json()))

        return Response(
            json.dumps({"myFiles": myFiles}),
            status=200,
            mimetype="application/json",
        )


class UpdatePlayerAPI(Resource):
    """
    Documents will be updated for last time played
    """


class DocumentAPI(Resource):
    """
    User can delete a Document (its DB record and stored files).
    """

    @jwt_required()
    def delete(self):
        try:
            email = get_jwt_identity()
            user = Users.objects.get(email=email)
            data = request.get_json(force=True)
            doc = Docs.objects.get(id=data["id"], user=user)

            # Remove stored document + generated audio from local storage.
            for name in (doc.doc_name, doc.female_audio_name, doc.male_audio_name):
                if name:
                    storage.delete_file(name)

            doc_name = doc.doc_name
            doc.delete()
            return Response(
                json.dumps({"success": True, "message": f"{doc_name} has been deleted."}),
                status=200,
                mimetype="application/json",
            )
        except Docs.DoesNotExist:
            return Response(json.dumps({"success": False, "message": "Document not found"}),
                            status=404, mimetype="application/json")
        except Exception as e:
            return Response(json.dumps({"success": False, "message": str(e)}),
                            status=500, mimetype="application/json")


class UpdateDocumentFavAPI(Resource):
    """
    Enables user to mark the document as a fav
    """
    def put(self): #Input DOC NAME
        try:
            data = request.get_json(force=True)
            print(data)
            doc = Docs.objects.get(id = data["id"])
            doc.fav = True
            doc.save()
            print(doc.fav)
            return Response(
                json.dumps({"message": doc.doc_name + " has been added to your favorites."}),
                status=200,
                mimetype="application/json",
            )
        except Docs.DoesNotExist:
            return Response(json.dumps({"success": False, "message": "Document not found"}),
                            status=404, mimetype="application/json")
        except Exception as e:
            return Response(json.dumps({"success": False, "message": str(e)}),
                            status=500, mimetype="application/json")
        
class UpdateDocumentUnFavAPI(Resource):
    """
    Enables user to mark the document as a fav
    """
    def put(self): #Input DOC NAME
        try:
            data = request.get_json(force=True)
            print(data)
            doc = Docs.objects.get(id = data["id"])
            doc.fav = False
            doc.save()
            print(doc.fav)
            return Response(
                json.dumps({"message": doc.doc_name + " has been removed from your favorites."}),
                status=200,
                mimetype="application/json",
            )
        except Docs.DoesNotExist:
            return Response(json.dumps({"success": False, "message": "Document not found"}),
                            status=404, mimetype="application/json")
        except Exception as e:
            return Response(json.dumps({"success": False, "message": str(e)}),
                            status=500, mimetype="application/json")

class GetAllFiles(Resource):
    """Gets all filenames in the Azure Blob Storage container"""

    def get(self):
        container = ContainerClient.from_connection_string(
            conn_str=connect_str, container_name=container_str
        )

        all_filenames = []
        blob_list = container.list_blobs()
        for blob in blob_list:
            all_filenames.append(blob.name)

        return {"filenames": all_filenames}


# mimeTYPE = https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types

