from flask import Response, request, jsonify
from werkzeug.wrappers import response
from werkzeug.utils import secure_filename
from database.models import Users
import json
from flask_restful import Resource
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required


class UserSignUpAPI(Resource):
    """
    User API for Signup via Email
    """

    def post(self):
        """
        Sign up endpoint for User to create account and generates hash password
        """
        # try:
        data = request.get_json(force=True)
        if data["password"] != data["confirmPassword"]:
            resp = Response()
            resp.status = 400
            resp.content_type = "application/json"
            resp.set_data(
                json.dumps({"error": "Password and confirm password do not match."})
            )
            return resp
        u = Users(
            email=data["email"],
            name=data["name"],
            password=generate_password_hash(data["password"], method="pbkdf2:sha256"),
            phone=data["phone"],
        ).save()
        resp = Response()
        resp.status = 200
        resp.content_type = "application/json"
        resp.set_data(
            json.dumps(
                {
                    "message": "Your account has successfully been created, please login!",
                }
            )
        )
        return resp
        # except Exception as e:
        #     return Response(
        #         json.dumps({"error": str(e)}),
        #         status=500,
        #         content_type="application/json",
        #     )


class UserLoginAPI(Resource):
    """
    User API for Login via Email
    """

    def post(self):
        """
        Login endpoint for User to login
        """
        data = request.get_json(force=True)
        print(data)
        user = Users.objects.get(email=data["email"])
        if check_password_hash(user.password, data["password"]):
            access_token = create_access_token(identity=user.email)
            resp = Response()
            resp.status = 200
            resp.content_type = "application/json"
            resp.set_data(
                json.dumps(
                    {
                        "userMeta": json.loads(user.to_json()),
                        "isLoggedIn": True,
                        "token": access_token,
                    }
                )
            )
            return resp
        resp = Response()
        resp.status = 401
        resp.content_type = "application/json"
        resp.set_data(
            json.dumps(
                {
                    "message": "Invalid credentials",
                }
            )
        )
        return resp


'''
    def get(self):
        """
        Login
        """
        try:
            data = request.args.get("email")
            u = Users.objects.get(email=data)
            return Response(u.to_json(), status=200, mimetype="application/json")
        except Exception as e:
            print(e)
            return Response(json.dumps(e), status=500, mimetype="application/json")

    def put(self):
        """
        This function updates a user information in mongo db for a given email
        """
        try:
            data = request.get_json(force=True)
            u = Users.objects.get(email=data["email"])
            u.first_name = data["first_name"]
            u.last_name = data["last_name"]
            u.save()
            return Response(
                json.dumps({"message": u.email + " information has been updated."}),
                status=200,
                mimetype="application/json",
            )
        except Exception as e:
            return Response(json.dumps(e), status=500, mimetype="application/json")

    def delete(self):
        """
        This function updates a user information in mongo db for a given email
        """
        try:
            data = request.get_json(force=True)
            u = Users.objects.get(email=data["email"])
            u.delete()
            return Response(
                json.dumps({"message": u.email + " has been deleted."}),
                status=200,
                mimetype="application/json",
            )
        except Exception as e:
            print(e.user_message)
            return Response(
                json.dumps(e.user_message), status=500, mimetype="application/json"
            )

'''
