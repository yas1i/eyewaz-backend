import io, requests
import os, uuid
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
import io
import wave
import docx2txt
#import soundfile as sf

connect_str = os.getenv("AZURE_CONNECTION_STRING")
container_str = os.getenv("AZURE_CONTAINER")

# Define the URL of the file you want to download
download_url = "https://eyewazstorage.blob.core.windows.net/eyewaz-dev/EyeWasWord.docx"

# Create a directory named '.temp' in the current working directory
temp_folder = ".temp"
os.makedirs(temp_folder, exist_ok=True)

# Get the filename from the download URL
filename = download_url.split("/")[-1]

# Construct the full path to save the downloaded file
download_path = os.path.join(temp_folder, filename)

# Download the file from the URL and save it to the download path
response = requests.get(download_url)
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

