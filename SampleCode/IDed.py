from mongoengine import connect
from bson import ObjectId

# Connect to your MongoDB database
connect('your_database_name', host='your_mongodb_uri')

# Iterate over existing documents and update the id field
for doc in Docs.objects:
    doc.id = ObjectId()
    doc.save()
