import os
from flask import Flask, render_template
from flask_restful import Api
from routes import initialize_routes
from dotenv import load_dotenv, find_dotenv
from flask_cors import CORS
from mongoengine import connect
from flask_jwt_extended import JWTManager

# from celery import Celery

load_dotenv(find_dotenv())

static_dir = str(os.path.abspath(os.path.join(__file__, "..", os.getenv("STATIC_DIR"))))
app = Flask(
    __name__, static_folder=static_dir, static_url_path="", template_folder=static_dir
)
# celery = Celery(
#     __name__, broker="redis://127.0.0.1:6379/0", backend="redis://127.0.0.1:6379/0"
# )

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")

jwt = JWTManager(app)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})
db = connect(host=os.getenv("MONGO_URI"))
api = Api(app)
initialize_routes(api)


@app.route("/")
def index():
    return render_template("index.html")


# @celery.task
# def divide(x, y):
#     import time

#     time.sleep(5)
#     return x / y
