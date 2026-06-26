"""
https://flask-restful.readthedocs.io/en/latest/
"""

from resources.user import (
    UserSignUpAPI, UserLoginAPI, VerifyOtpAPI, ResendOtpAPI,
    ForgotPasswordAPI, ResetPasswordAPI,
)
from resources.account import ProfileAPI, VoicesAPI
from resources.documents import DocumentTransSpeechAPI, DocumentAPI
from resources.documents import UpdateDocumentFavAPI, UpdateDocumentUnFavAPI
from resources.playback import PausePlaybackAPI
from resources.folder import Folder, FolderApi
from resources.web import ReadUrlAPI, TranslateTextAPI, SpeakAPI
from resources.assistant import AssistantAPI, AssistantConfigAPI
from resources.billing import (
    UsageAPI, DevPlanAPI,
    PayPalConfigAPI, PayPalActivateAPI, PayPalCancelAPI, PayPalSetupAPI, PayPalWebhookAPI,
    StripeConfigAPI, StripeCheckoutAPI, StripeWebhookAPI,
)
from resources.dialects import DialectsAPI, DialectCloneAPI
from resources.voicebank import VoiceBankClipAPI, VoiceBankStatsAPI, VoiceBankExportAPI, VoiceBankDoneAPI
from resources.webauthn_res import (
    WebAuthnRegisterOptions, WebAuthnRegisterVerify,
    WebAuthnLoginOptions, WebAuthnLoginVerify,
)


def initialize_routes(api):
    api.add_resource(UserSignUpAPI, "/api/signup")
    api.add_resource(UserLoginAPI, "/api/login")
    api.add_resource(VerifyOtpAPI, "/api/verify-otp")
    api.add_resource(ResendOtpAPI, "/api/resend-otp")
    api.add_resource(ForgotPasswordAPI, "/api/forgot-password")
    api.add_resource(ResetPasswordAPI, "/api/reset-password")
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
    api.add_resource(ProfileAPI, "/api/profile")
    api.add_resource(VoicesAPI, "/api/voices")
    api.add_resource(AssistantAPI, "/api/assistant")
    api.add_resource(AssistantConfigAPI, "/api/assistant/config")
    api.add_resource(UsageAPI, "/api/usage")
    api.add_resource(DevPlanAPI, "/api/dev/plan")
    api.add_resource(DialectsAPI, "/api/dialects")
    api.add_resource(DialectCloneAPI, "/api/dialects/clone")
    api.add_resource(VoiceBankClipAPI, "/api/voicebank/clip")
    api.add_resource(VoiceBankStatsAPI, "/api/voicebank/stats")
    api.add_resource(VoiceBankDoneAPI, "/api/voicebank/done")
    api.add_resource(VoiceBankExportAPI, "/api/voicebank/export")
    api.add_resource(PayPalConfigAPI, "/api/paypal/config")
    api.add_resource(PayPalActivateAPI, "/api/paypal/activate")
    api.add_resource(PayPalCancelAPI, "/api/paypal/cancel")
    api.add_resource(PayPalSetupAPI, "/api/paypal/setup")
    api.add_resource(PayPalWebhookAPI, "/api/paypal/webhook")
    api.add_resource(StripeConfigAPI, "/api/stripe/config")
    api.add_resource(StripeCheckoutAPI, "/api/stripe/checkout")
    api.add_resource(StripeWebhookAPI, "/api/stripe/webhook")
    api.add_resource(WebAuthnRegisterOptions, "/api/webauthn/register/options")
    api.add_resource(WebAuthnRegisterVerify, "/api/webauthn/register/verify")
    api.add_resource(WebAuthnLoginOptions, "/api/webauthn/login/options")
    api.add_resource(WebAuthnLoginVerify, "/api/webauthn/login/verify")