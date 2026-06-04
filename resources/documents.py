import io, requests
import os
import storage
from helpers import ConvertEnglishtoUrdu, TexttoSpeech_Female, TexttoSpeech_Male, UploadOnAzure, ImagetoText
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

def translationSpeechTask(f):
    blob_client = UploadOnAzure(f, f.filename)

    data = blob_client.download_blob()
    ext = blob_client.blob_name.split(".")[-1]
    url = blob_client.url
    text = ""
    if ext == "docx":
        # Create a directory named '.temp' in the current working directory
        temp_folder = ".temp"
        os.makedirs(temp_folder, exist_ok=True)

        # Get the filename from the download URL
        filename = url.split("/")[-1]

        # Construct the full path to save the downloaded file
        download_path = os.path.join(temp_folder, filename)

        # Download the file from the URL and save it to the download path
        response = requests.get(url)
        if response.status_code == 200:
            with open(download_path, "wb") as file:
                file.write(response.content)
            print(f"File downloaded and saved to: {download_path}")
        else:
            print("Failed to download the file.")

        # Path to the DOCX file
        docx_file_path = download_path

        # Extract text from the DOCX file as a UTF-8 encoded string
        utf8_text = docx2txt.process(docx_file_path)

        # Print or do something with the UTF-8 encoded text
        print(utf8_text)
        text = utf8_text
        # Clean up: Delete the .temp folder and its contents
        try:
            shutil.rmtree(temp_folder)
            print(f"Deleted {temp_folder} and its contents.")
        except Exception as e:
            print(f"An error occurred while deleting {temp_folder}: {e}")

    elif ext == "txt":
        text = data.read()
        text = str(text, encoding="utf-8")
        print(text)
    # print(clean_text(text))
    elif ext == "pdf":
        # Define the URL of the PDF file you want to download
        pdf_download_url = url
        # Create a directory named '.temp' in the current working directory
        temp_folder = ".temp"
        os.makedirs(temp_folder, exist_ok=True)

        # Get the filename from the download URL
        filename = pdf_download_url.split("/")[-1]

        # Construct the full path to save the downloaded PDF file
        pdf_download_path = os.path.join(temp_folder, filename)

        # Download the PDF file from the URL and save it to the download path
        response = requests.get(pdf_download_url)
        if response.status_code == 200:
            with open(pdf_download_path, "wb") as file:
                file.write(response.content)
            print(f"PDF file downloaded and saved to: {pdf_download_path}")
        else:
            print("Failed to download the PDF file.")

        # Open the downloaded PDF file in binary mode
        with open(pdf_download_path, "rb") as pdf_file:
            # Create a PDF reader object
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # Initialize an empty string to store the extracted text
            text_content = ""

            # Iterate through pages in the PDF and extract text
            for page_number in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_number]
                text_content += page.extract_text()

        # Convert the text content to UTF-8 encoded string
        utf8_text = text_content.encode("utf-8")

        # Print or do something with the UTF-8 encoded text
        print(utf8_text.decode("utf-8"))
        text = utf8_text.decode("utf-8")
        # Clean up: Delete the .temp folder and its contents
        try:
            shutil.rmtree(temp_folder)
            print(f"Deleted {temp_folder} and its contents.")
        except Exception as e:
            print(f"An error occurred while deleting {temp_folder}: {e}")
    elif ext == "png" or ext == "jpg" or ext == "jpeg":
        # Send raw image bytes to Azure Vision (the file is stored locally,
        # so a localhost URL would be unreachable by Azure's cloud service).
        text = ImagetoText(blob_client.read_bytes())
        print(text)

    Trans_text, lang = ConvertEnglishtoUrdu(text)
    print(text)
    female_audio = TexttoSpeech_Female(Trans_text)
    female_audio_data = female_audio.audio_data
    female_audio_duration = get_audio_duration_from_bytes(female_audio_data)
    print("FEMALE AUDIO DURATION", female_audio_duration)
    
    male_audio = TexttoSpeech_Male(Trans_text)
    male_audio_data = male_audio.audio_data
    male_audio_duration = get_audio_duration_from_bytes(male_audio_data)
    print("MALE AUDIO DURATION", male_audio_duration)
    # Generate a unique filename
    female_audio_filename = blob_client.blob_name.split(".")[0] + "_female.wav"
    female_audio_blob_client = UploadOnAzure(female_audio_data, female_audio_filename)
    
    male_audio_filename = blob_client.blob_name.split(".")[0] + "_male.wav"
    male_audio_blob_client = UploadOnAzure(male_audio_data, male_audio_filename)
    return text,Trans_text,lang,female_audio_duration,blob_client,female_audio_blob_client,male_audio_blob_client,male_audio_duration

class DocumentTransSpeechAPI(Resource):
    """Uploads file to Azure Blob Storage"""

    @jwt_required()
    def post(self):
        """
        Translates & Generates Speech for docs, pdfs, jpg, pngs for a user
        """
        # try:
        f = request.files["file"]
        email = get_jwt_identity()
        user = Users.objects.get(email=email)

        text,Trans_text,lang,female_audio_duration,blob_client,female_audio_blob_client,male_audio_blob_client,male_audio_duration = translationSpeechTask(f)
        data = {
            "doc_url": blob_client.url,
            "doc_name": blob_client.blob_name,
            "doc_extension": blob_client.blob_name.split(".")[-1],
            "eng_text": text,
            "tran_text": Trans_text,
            "lang": lang,
            "trans_lang": "ur-PK",
            "female_audio_url": female_audio_blob_client.url,
            "female_audio_name": female_audio_blob_client.blob_name,
            "female_audio_extension": female_audio_blob_client.blob_name.split(".")[-1],
            "female_audio_duration": female_audio_duration,
            "male_audio_url": male_audio_blob_client.url,
            "male_audio_name": male_audio_blob_client.blob_name,
            "male_audio_extension": male_audio_blob_client.blob_name.split(".")[-1],
            "male_audio_duration": male_audio_duration,
            "message": blob_client.blob_name + " Is Uploaded",
        }
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

