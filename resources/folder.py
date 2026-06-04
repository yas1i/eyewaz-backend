from bson import ObjectId
from flask import request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restful import Resource
from database.models import Users, Folders, Docs
import uuid

class Folder(Resource):
    """ALL FOLDER IMPLEMENTATION"""
    @jwt_required()
    def post(self):
        try:
            email = get_jwt_identity()
            user = Users.objects.get(email=email)
            data = request.get_json(force=True)
            
            existing_folder = Folders.objects(user=user, folder_name=data.get("folder_name")).first()
            
            if not existing_folder:
                print("Creating a new folder")
                folder_name = data.get("folder_name")
                new_folder = Folders(user=user, folder_name=folder_name, id=str(uuid.uuid4()))
                new_folder.save()

                response_data = {'success': True, 'message': f'Folder "{folder_name}" created for the user', 'folder_id': str(new_folder.id)}
                return make_response(jsonify(response_data))
            else:
                response_data = {'success': False, 'message': 'Folder already exists for the user'}
                return make_response(jsonify(response_data), 400)
        except Users.DoesNotExist:
            return make_response(jsonify({'success': False, 'message': 'User not found'}), 404)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return make_response(jsonify({'success': False, 'message': 'Internal server error'}), 500)
    
    @jwt_required()
    def get(self):
        try:
            email = get_jwt_identity()
            user = Users.objects.get(email=email)
            folderlist = Folders.objects(user=user)
            
            fileslist = []
            folders = []
            for folder in folderlist:
                print(folder.folder_name)
                
                for files in folder.files:
                    print(files.doc_name)
                    jsonfile = files.to_dict()
                    fileslist.append(jsonfile)
                
                folder_data = {'folder_name': folder.folder_name, 'files': fileslist}
                folders.append(folder_data)
                #print("folder_DATA = ",folder_data)
                #print(fileslist)       
                fileslist = []
            print(folders)
            return jsonify({'success': True, 'folders': folders})
        except Exception as e:
            return make_response(jsonify({'success': False, 'message': e}))

    @jwt_required()
    def delete(self):
        try:
            email = get_jwt_identity()
            user = Users.objects.get(email = email)
            data = request.get_json(force=True)
            
            existing_folder = Folders.objects(user=user, folder_name=data.get("folder_name")).first()
            
            if existing_folder:
                print(True)
                print(existing_folder.id)
                existing_folder.delete()
                return jsonify({'success': 'True', 'message': f'Folder "{existing_folder.folder_name}" has been succesfully deleted.'})
            else:
                return jsonify({'success':'False'})
        except Exception as e:
            print(e)
        
        
class FolderApi(Resource):
    @jwt_required()
    def post(self):
            try:
                # Get the user based on the JWT identity
                email = get_jwt_identity()
                user = Users.objects.get(email=email)

                # Get data from the request
                data = request.get_json(force=True)
                folder_name = data.get("folder_name", "")
                file_ids = data.get("file_ids", [])

                # Check if the folder exists for the user
                folder = Folders.objects(user=user, folder_name=folder_name).first()

                if folder:
                    # Iterate over the file_ids and add each file to the folder
                    for file_id in file_ids:
                        try:
                            file_obj = Docs.objects.get(id=str(file_id))
                            # Check if the file_obj is not None
                            print(file_obj.id)
                            if file_obj:
                                # Add the file to the folder
                                folder.add_file(file_obj)
                            else:
                                # Handle the case where the document does not exist
                                return make_response(jsonify({'success': False, 'message': f'Document with ID {file_id} does not exist'}), 404)
                        except Docs.DoesNotExist:
                            # Handle the case where the document does not exist
                            return make_response(jsonify({'success': False, 'message': f'Document with ID {file_id} does not exist'}), 404)

                    # Save the updated folder
                    folder.save()

                    response_data = {'success': True, 'message': 'Files added to the folder successfully'}
                    return make_response(jsonify(response_data))
                else:
                    response_data = {'success': False, 'message': f'Folder "{folder_name}" not found for the user'}
                    return make_response(jsonify(response_data), 404)

            except Users.DoesNotExist:
                return make_response(jsonify({'success': False, 'message': 'User not found'}), 404)
            except Exception as e:
                print(f"An error occurred: {str(e)}")
                return make_response(jsonify({'success': False, 'message': 'Internal server error'}), 500)
        
        

    @jwt_required()
    def get(self):
        try:
            email = get_jwt_identity()
            user = Users.objects.get(email=email)
            folderlist = Folders.objects(user=user)
            
            fileslist = []
            folders = []
            for folder in folderlist:
                print(folder.folder_name)
                
                for files in folder.files:
                    print(files.doc_name)
                    jsonfile = files.to_dict()
                    fileslist.append(jsonfile)
                
                folder_data = {'folder_name': folder.folder_name, 'files': fileslist}
                folders.append(folder_data)
                #print("folder_DATA = ",folder_data)
                #print(fileslist)       
                fileslist = []
            print(folders)
            return jsonify({'success': True, 'folders': folders})
        except Exception as e:
            return make_response(jsonify({'success': False, 'message': e}))
            
    

            


'''    
    @jwt_required()
    def get(self):
        try:
            email = get_jwt_identity()
            user = Users.objects.get(email=email)
            folderlist = Folders.objects(user=user)

            folders_data = []
            for folder in folderlist:
                # Assuming you have a 'name' field in your Folder model
                files_data = []
                for file_id in folder.files:
                    file_obj = Docs.objects.get(id=id)
                    # Convert Docs object to dictionary or serialize it appropriately
                    file_data = {
                        'doc_name': file_obj.doc_name,
                        'doc_url': file_obj.doc_url,
                        # Add other fields as needed
                    }
                    files_data.append(file_data)

                folder_data = {'folder_name': folder.folder_name, 'files': files_data}
                folders_data.append(folder_data)

            return {'success': True, 'folders': folders_data}
        except Users.DoesNotExist:
            return {'success': False, 'message': 'User not found'}, 404
        except Folders.DoesNotExist:
            return {'success': False, 'message': 'No folders found for the user'}, 404
        except Docs.DoesNotExist:
            return {'success': False, 'message': 'Document not found'}, 404
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return {'success': False, 'message': 'Internal server error'}, 500
'''