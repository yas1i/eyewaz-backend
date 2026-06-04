# from distutils.command.upload import upload
# from flask import Response, request, jsonify
# from database.models import Jobs, Users
# from database.db import connect_db
# import json
# from flask_restful import Resource

# import uuid
# import boto3
# import json
# import base64
# import os
# from dotenv import load_dotenv,find_dotenv
# load_dotenv(find_dotenv())

# class JobsAPI(Resource):
         
#     def post(self):
#         '''
#         Endpoint creates a new Job
#         '''
#         data = request.get_json(force=True)
#         job_id = str(uuid.uuid4())
#         Jobs(job_id = job_id,
#             email=data['email'],
#             description=data['description'],
#             s3_input=data['s3_input'],
#             x_col = data['x_col'],
#             y_col = data['y_col'],
#             id_col = data['id_col'],
#             csv_lines = data['csv_lines']
#         ).save()

#         resp=Response()
#         #resp.status = 200
#         resp.content_type = 'application/json'
#         resp.set_data(json.dumps({'message':data['email']+' has been sucessfully created in new Job','job_id':job_id}))
#         return resp
        
         
#     def get(self):
#         '''
#         Get the a created Job based on UID
#         '''
#         data = request.args.get("job_id")
#         u = Jobs.objects.get(job_id=data)
#         json_data = u.to_json()
#         resp=Response()
#         resp.status = 200
#         resp.content_type = 'application/json'
#         resp.set_data(json_data)
#         return resp
        
#     def put(self):
#         '''
#         FOR updating job_id output URL after creating the job
#         '''
#         data = request.get_json(force=True)
#         u = Jobs.objects.get(job_id=data['job_id'])

#         u.s3_input = data['s3_input']

#         lambda_results = {}

#         lambda_results['job_id'] = data['job_id']
#         lambda_results['s3_input'] = data['s3_input']

#         #call the lambda function here
#         # Hit the lamda function
        
#         client = boto3.client('lambda',
#                       aws_access_key_id=os.getenv('AWS_ACCESS_KEY'), 
#                       aws_secret_access_key=os.getenv('AWS_SECRET_KEY'), 
#                       region_name='eu-west-2'
#                      )
#         d = {
#             "body": {
#                 "user_id": data['job_id'],
#                 "s3_bucket": "mission-objective-csv-bucket",
#                 "csv_key": data['s3_input'],
#                 "id_column": u.id_col,
#                 "target_column": u.y_col,
#                 }
#             }

#         s = json.dumps(d)
#         s64 = base64.b64encode(s.encode('utf-8'))

#         if(os.getenv("MODE")=='prod'):
#             LAMBDA_URL = os.getenv("MO_LAMBDA_PROD")
#         else:
#             LAMBDA_URL = os.getenv("MO_LAMBDA_DEV")

#         response = client.invoke(
#             FunctionName=LAMBDA_URL,
#             Payload=json.dumps(d)
#         )
#         payload = json.loads(response['Payload'].read().decode("utf-8"))
#         print(payload)
#         try:
#             if (int(payload['statusCode'])==200):
#                 print("Successfully Executed lambda, whoop!")
#                 job_id = payload['body']['userId']
#                 uploadFolder = payload['body']['uploadFolder']
#                 uploadBucket = payload['body']['uploadBucket']
#                 csvKey = payload['body']['csvKey']
#                 chartKeys = payload['body']['chartKeys']

#                 topModel = payload['body']['topModel']
#                 allModels = payload['body']['allModels']
#                 MODELS_TO_COMPARE = payload['body']['MODELS_TO_COMPARE']
#                 MODEL_METRIC = payload['body']['MODEL_METRIC']
#                 lambda_results['status']=True
#                 lambda_results['job_id'] = job_id
#                 lambda_results['uploadFolder'] = uploadFolder
#                 lambda_results['uploadBucket'] = uploadBucket
#                 lambda_results['csvKey'] = csvKey
#                 lambda_results['chartDir'] = chartKeys
                
#                 lambda_results['allModels'] = allModels
#                 lambda_results['topModels'] = topModel
#                 lambda_results['models_to_compare'] = MODELS_TO_COMPARE
#                 lambda_results['model_metric'] = MODEL_METRIC
#                 u.status=True
#                 u.chartDir = chartKeys
#                 u.allModels = allModels
#                 u.topModels = topModel
#                 u.models_to_compare = MODELS_TO_COMPARE
#                 u.model_metric = MODEL_METRIC
#                 u.s3_output =csvKey
#                 #Updating a Successful Count for Total Jobs in User
#                 user = Users.objects.get(email=u.email)
#                 user.total_missions = user.total_missions + 1
#                 user.total_lines = user.total_lines + u.csv_lines
#                 user.save()
#             u.save()
#             resp=Response()
#             # resp.status = 200
#             resp.content_type = 'application/json'
#             resp.set_data(json.dumps(lambda_results))
#             return resp
#         except:
#             u.status=False
#             u.error=payload['errorMessage']
#             u.reason=payload['errorMessage']
#             lambda_results['error']=u.error
#             lambda_results['status']=False
#             lambda_results['reason']=u.error
#             resp=Response()
#             # resp.status = 200
#             resp.content_type = 'application/json'
#             resp.set_data(json.dumps(lambda_results))
#             return resp



#     def delete(self):
#         data = request.args.get('job_id')
#         print(data)
#         try:
#             Jobs.objects.get(job_id=data).delete()
#             r={'message': data+" Job ID has succesfully deleted"}
#             return Response(json.dumps(r))
#         except:
#             r={'error': data+" Job ID couldn't be deleted"}
#             return Response(json.dumps(r))


#         #delete from s3 all training / model data for job_id

# class JobStatusApi(Resource):
         
#     def get(self):
#         '''
#         For React Site to get status of Job
#         '''
#         data = request.get_json(force=True)
#         u = Jobs.objects.get(job_id=data['job_id'])
#         json_data = u.status
#         resp=Response()
#         resp.status = 200
#         resp.content_type = 'application/json'
#         resp.set_data(json.dumps({"status":json_data}))
#         return resp

