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
    phone = StringField(max_length=12, unique=True)
    password = StringField(required=True, max_length=250)
    objects = QuerySetManager()


class Docs(Document):
    id = StringField(primary_key=True)
    user = ReferenceField(Users)
    doc_url = StringField(max_length=100, default="")
    female_audio_url = StringField(max_length=100)
    female_audio_name = StringField(max_length=100)
    female_audio_extension = StringField(max_length=100)
    male_audio_url = StringField(max_length=100)
    male_audio_name = StringField(max_length=100)
    male_audio_extension = StringField(max_length=100)
    doc_name = StringField(max_length=30, default="")
    doc_extension = StringField(max_length=10)
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
    folder_name = StringField(max_length=20, unique=True)
    files = ListField(ReferenceField(Docs))
    objects = QuerySetManager()

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
