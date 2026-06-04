import os
import requests
import PyPDF2
import shutil

# Define the URL of the PDF file you want to download
pdf_download_url = "https://eyewazstorage.blob.core.windows.net/eyewaz-dev/Assignment.pdf"

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

# Clean up: Delete the .temp folder and its contents
try:
    shutil.rmtree(temp_folder)
    print(f"Deleted {temp_folder} and its contents.")
except Exception as e:
    print(f"An error occurred while deleting {temp_folder}: {e}")
