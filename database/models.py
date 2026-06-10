from enum import unique
from mongoengine import (
    ReferenceField,
    Document,
    DictField,
    EmailField,
    BooleanField,
    StringField,
    ListField,
    DateTimeField,
    QuerySetManager,
    FloatField,
    IntField,
    UUIDField,
    ObjectIdField
)
from datetime import datetime

"""
http://docs.mongoengine.org/tutorial.html?highlight=string
"""


class Users(Document):
    name = StringField(max_length=30, default="")
    email = EmailField(required=True, unique=True)
    phone = StringField(max_length=12)
    password = StringField(required=True, max_length=250)
    # Email 2-step verification
    is_verified = BooleanField(default=False)
    otp_hash = StringField()
    otp_expires = DateTimeField()
    otp_purpose = StringField(max_length=20)
    # Listening preferences
    pref_engine = StringField(max_length=10, default="azure")      # azure | browser
    pref_language = StringField(max_length=10, default="ur-PK")
    pref_voice = StringField(default="ur-PK-UzmaNeural")
    pref_rate = FloatField(default=1.0)                            # speed multiplier
    # Morning-assistant to-do lists
    todo_weekday = StringField(default="")
    todo_weekend = StringField(default="")
    # Membership / billing
    plan = StringField(max_length=20, default="free")    # free | monthly | supermax
    plan_until = DateTimeField()                          # paid plan expiry (None = free/forever)
    usage_day = StringField(max_length=10, default="")    # "YYYY-MM-DD" of the current count
    usage_count = IntField(default=0)                     # commands used today
    paypal_sub_id = StringField()                         # PayPal subscription id
    stripe_customer_id = StringField()                    # Stripe customer (card / Klarna)
    stripe_sub_id = StringField()                         # Stripe subscription id
    # Passkeys (Face ID / Touch ID / fingerprint) — WebAuthn public-key creds.
    # Each: {id, public_key, sign_count} (base64url strings + int).
    webauthn_credentials = ListField(DictField())
    objects = QuerySetManager()

    def preferences(self):
        return {
            "engine": self.pref_engine or "azure",
            "language": self.pref_language or "ur-PK",
            "voice": self.pref_voice or "ur-PK-UzmaNeural",
            "rate": self.pref_rate or 1.0,
        }


class AppSettings(Document):
    """Singleton app config persisted in the DB (e.g. PayPal plan ids created at
    runtime), so payment setup needs no env round-trip or redeploy."""
    key = StringField(primary_key=True, default="singleton")
    paypal_product_id = StringField()
    paypal_plan_monthly = StringField()
    paypal_plan_supermax = StringField()
    assistant_enabled = BooleanField(default=False)   # admin toggle, off by default
    objects = QuerySetManager()


class DialectVoice(Document):
    """A cloned dialect voice in the EYEWAZ voice bank (Phase 2).
    dialect_id matches an entry in resources/dialects.CATALOG."""
    dialect_id = StringField(primary_key=True)
    engine = StringField(max_length=20, default="elevenlabs")
    voice_id = StringField()                  # provider voice id
    speaker = StringField(max_length=80)      # who recorded it
    consent_at = DateTimeField()              # when consent was confirmed
    created_at = DateTimeField(default=datetime.utcnow)
    objects = QuerySetManager()


class VoiceClip(Document):
    """One recorded utterance in the online voice bank — the raw material for
    training a dialect/language TTS voice. Contributors (native speakers across
    provinces) record via the web recorder, which uploads here."""
    lang = StringField(max_length=40, default="urdu")     # dialect/language id
    speaker = StringField(max_length=120, default="")     # speaker name/id
    gender = StringField(max_length=10, default="")        # male | female
    sentence_id = StringField(max_length=20, default="")   # e.g. "0001"
    transcript = StringField(default="")                   # exact text read
    filename = StringField(default="")                     # stored wav filename
    duration = FloatField(default=0.0)                      # seconds
    consent_at = DateTimeField()                            # consent timestamp
    contributor = StringField(max_length=160, default="")  # who uploaded (email/handle)
    created_at = DateTimeField(default=datetime.utcnow)
    meta = {"indexes": ["lang", "speaker", ("lang", "speaker", "sentence_id")]}
    objects = QuerySetManager()


class Docs(Document):
    id = StringField(primary_key=True)
    user = ReferenceField(Users)
    # Generous limits: local-storage URLs and uuid-prefixed filenames are long.
    doc_url = StringField(default="")
    female_audio_url = StringField()
    female_audio_name = StringField()
    female_audio_extension = StringField(max_length=20)
    male_audio_url = StringField()
    male_audio_name = StringField()
    male_audio_extension = StringField(max_length=20)
    doc_name = StringField(default="")
    doc_extension = StringField(max_length=20)
    lang = StringField(max_length=10)
    trans_lang = StringField(max_length=10)
    trans_text = StringField(max_length=16777215)
    eng_text = StringField(max_length=16777215)
    folder_in_app = StringField(max_length=10)
    createdAt = DateTimeField(default=datetime.utcnow)
    female_audio_duration = IntField(min_value=None)
    male_audio_duration = IntField(min_value=None)
    fav = BooleanField()
    objects = QuerySetManager()
    lastplayedtime = StringField(max_length=40, default="00:00:00")
    bookmark = StringField(max_length=40, default="00:00:00")
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user': str(self.user.id),  # Assuming 'user' is a ReferenceField
            'doc_url': self.doc_url,
            'female_audio_url': self.female_audio_url,
            'female_audio_name': self.female_audio_name,
            'female_audio_extension': self.female_audio_extension,
            'male_audio_url': self.male_audio_url,
            'male_audio_name': self.male_audio_name,
            'male_audio_extension': self.male_audio_extension,
            'doc_name': self.doc_name,
            'doc_extension': self.doc_extension,
            'lang': self.lang,
            'trans_lang': self.trans_lang,
            'trans_text': self.trans_text,
            'eng_text': self.eng_text,
            'folder_in_app': self.folder_in_app,
            'createdAt': self.createdAt.isoformat(),
            'female_audio_duration': self.female_audio_duration,
            'male_audio_duration': self.male_audio_duration,
            'fav': self.fav,
            'lastplayedtime': self.lastplayedtime,
            'bookmark': self.bookmark,
            # ... other fields ...
        }
       
    
class Folders(Document):
    id = StringField(primary_key=True)
    user = ReferenceField(Users)
    # Folder names are unique per-user (not globally), so different users can
    # each have e.g. a "Books" folder.
    folder_name = StringField(max_length=20)
    files = ListField(ReferenceField(Docs))
    objects = QuerySetManager()
    meta = {
        "indexes": [
            {"fields": ("user", "folder_name"), "unique": True},
        ]
    }

    def add_file(self, file_instance):
        if file_instance not in self.files:
            self.files.append(file_instance)

    def remove_file(self, file_instance):
        if file_instance in self.files:
            self.files.remove(file_instance)

class Images(Document):
    user = ReferenceField(Users)
    img_name = StringField(max_length=20)
    img_url = StringField(max_length=200, default="")
    img_extension = StringField(max_length=20)
    raw_text = StringField(max_length=5000)
    audio_url = StringField(max_length=100)
    audio_name = StringField(max_length=100)
    audio_extension = StringField(max_length=100)
    lang = StringField(max_length=10)
    trans_lang = StringField(max_length=10)
    trans_text = StringField(max_length=5000)
