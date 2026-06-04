from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from flask import jsonify
from msrest.authentication import CognitiveServicesCredentials

import os
import time

print("hello")

'''
Authenticate
Authenticates your credentials and creates a client.
'''
subscription_key = "190b36a9358d4ae4addb1466cae09940"
endpoint = "https://eyewaz-vision.cognitiveservices.azure.com/"

computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))
'''
END - Authenticate
'''
def ImagetoText():
    print("===== Read File - remote =====")
    # Get an image with text
    read_image_url = "https://i.stack.imgur.com/t3qWG.png"
    print(read_image_url)

    # Call API with URL and raw response (allows you to get the operation location)
    read_response = computervision_client.read(read_image_url,  raw=True)
    print(read_response)
   # print(jsonify(read_response))

    # Get the operation location (URL with an ID at the end) from the response
    read_operation_location = read_response.headers["Operation-Location"]
    # Grab the ID from the URL
    operation_id = read_operation_location.split("/")[-1]

    # Call the "GET" API and wait for it to retrieve the results 
    while True:
        read_result = computervision_client.get_read_result(operation_id)
        if read_result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)
    returnsString =  ""
    # Print the detected text, line by line
    if read_result.status == OperationStatusCodes.succeeded:
        for text_result in read_result.analyze_result.read_results:
            for line in text_result.lines:
                returnsString = returnsString + line.text
                #print(line.text)
                #print(line.bounding_box)
            print(returnsString)
    print()
    '''
    END - Read File - remote
    '''
ImagetoText()