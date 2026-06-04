"""
https://flask-restful.readthedocs.io/en/latest/
"""

from resources.user import UserSignUpAPI, UserLoginAPI, VerifyOtpAPI, ResendOtpAPI
from resources.documents import DocumentTransSpeechAPI, DocumentAPI
from resources.documents import UpdateDocumentFavAPI, UpdateDocumentUnFavAPI
from resources.playback import PausePlaybackAPI
from resources.folder import Folder, FolderApi
from resources.web import ReadUrlAPI, TranslateTextAPI, SpeakAPI


def initialize_routes(api):
    api.add_resource(UserSignUpAPI, "/api/signup")
    api.add_resource(UserLoginAPI, "/api/login")
    api.add_resource(VerifyOtpAPI, "/api/verify-otp")
    api.add_resource(ResendOtpAPI, "/api/resend-otp")
    api.add_resource(DocumentTransSpeechAPI, "/api/document-translation-and-speech")
    api.add_resource(DocumentAPI, "/api/document")
    api.add_resource(UpdateDocumentFavAPI, "/api/fav-document")
    api.add_resource(UpdateDocumentUnFavAPI, "/api/unfav-document")
    api.add_resource(PausePlaybackAPI, "/api/playback-time-record")
    api.add_resource(Folder, "/api/folder")
    api.add_resource(FolderApi,"/api/files-folders")
    api.add_resource(ReadUrlAPI, "/api/read-url")
    api.add_resource(TranslateTextAPI, "/api/translate")
    api.add_resource(SpeakAPI, "/api/speak")