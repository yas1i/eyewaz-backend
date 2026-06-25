import os
from flask import Flask, render_template, send_from_directory, redirect, abort
from flask_restful import Api
from routes import initialize_routes
from dotenv import load_dotenv, find_dotenv
from flask_cors import CORS
from mongoengine import connect
from flask_jwt_extended import JWTManager
import storage

# from celery import Celery

# Load .env from this file's directory so the app works regardless of the
# process working directory (dev tooling, gunicorn, containers, etc.).
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))
load_dotenv(find_dotenv(), override=False)  # fall back to a discovered .env

static_dir = str(os.path.abspath(os.path.join(__file__, "..", os.getenv("STATIC_DIR", "templates/"))))
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

# connect=False defers the actual connection so a bad/unreachable MONGO_URI
# doesn't crash startup; wrap it too so a malformed URI just logs a warning.
try:
    # serverSelectionTimeoutMS keeps requests from hanging when the DB is
    # unreachable (e.g. Atlas IP allow-list expired) — they fail fast instead.
    db = connect(host=os.getenv("MONGO_URI"), connect=False, serverSelectionTimeoutMS=5000)
except Exception as e:
    print(f"WARNING: MongoDB connection setup failed: {e}", flush=True)
    db = None
api = Api(app)
initialize_routes(api)


@app.route("/")
def index():
    # Public marketing landing page. The app itself lives at /app.
    return _no_cache(send_from_directory(WEBAPP_DIR, "home.html"))


@app.route("/about")
def about_page():
    return _no_cache(send_from_directory(WEBAPP_DIR, "about.html"))


@app.route("/contact")
def contact_page():
    return _no_cache(send_from_directory(WEBAPP_DIR, "contact.html"))


@app.route("/site.css")
def site_css():
    return _no_cache(send_from_directory(WEBAPP_DIR, "site.css"))


@app.route("/how-it-works")
def how_it_works_page():
    return _no_cache(send_from_directory(WEBAPP_DIR, "how-it-works.html"))


@app.route("/why-us")
def why_us_page():
    return _no_cache(send_from_directory(WEBAPP_DIR, "why-us.html"))


@app.route("/download")
def download_page():
    return _no_cache(send_from_directory(WEBAPP_DIR, "download.html"))


@app.route("/site-logo.js")
def site_logo_js():
    return _no_cache(send_from_directory(WEBAPP_DIR, "site-logo.js"))


@app.route("/robots.txt")
def robots_txt():
    return send_from_directory(WEBAPP_DIR, "robots.txt", mimetype="text/plain")


@app.route("/BingSiteAuth.xml")
def bing_site_auth():
    return send_from_directory(WEBAPP_DIR, "BingSiteAuth.xml", mimetype="application/xml")


@app.route("/sitemap.xml")
def sitemap_xml():
    return send_from_directory(WEBAPP_DIR, "sitemap.xml", mimetype="application/xml")


@app.route("/favicon.ico")
def favicon():
    # Browsers ask for /favicon.ico at the root; serve the logo favicon.
    return send_from_directory(os.path.join(WEBAPP_DIR, "assets"),
                               "eyewaz-favicon.png", mimetype="image/png")


@app.route("/files/<path:filename>")
def serve_file(filename):
    """Serve uploaded documents and generated audio from local storage."""
    return send_from_directory(storage.UPLOAD_DIR, filename)


# --- Accessible web client (served same-origin so /api and /files just work) ---
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")


def _no_cache(resp):
    # Always serve fresh web-client assets during development so HTML/JS/CSS
    # never get out of sync in the browser cache.
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/app")
@app.route("/app/")
def webapp_index():
    return _no_cache(send_from_directory(WEBAPP_DIR, "index.html"))


@app.route("/app/<path:filename>")
def webapp_static(filename):
    return _no_cache(send_from_directory(WEBAPP_DIR, filename))


# --- Voice recorder (contributors collect into the online voice bank) ---
RECORDER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts-train", "recorder")


@app.route("/record")
def recorder_redirect():
    # Redirect to the trailing-slash form so relative asset URLs in index.html
    # (recorder.js, sentences.js) resolve under /record/ instead of the site root.
    return redirect("/record/", code=308)


@app.route("/record/")
def recorder_index():
    return _no_cache(send_from_directory(RECORDER_DIR, "index.html"))


@app.route("/record/<path:filename>")
def recorder_static(filename):
    return _no_cache(send_from_directory(RECORDER_DIR, filename))


@app.route("/privacy")
def privacy():
    # Public privacy policy (required for the app stores).
    return send_from_directory(WEBAPP_DIR, "privacy.html")


@app.route("/.well-known/assetlinks.json")
def assetlinks():
    # Digital Asset Links — verifies the Android TWA (Play Store) owns this domain.
    return send_from_directory(os.path.join(WEBAPP_DIR, ".well-known"),
                               "assetlinks.json", mimetype="application/json")


@app.route("/<filename>")
def site_verification(filename):
    # Search engine verification files served at the site root.
    # Google: googleXXXX.html   Bing: BingSiteAuth.xml
    # Strictly allow-listed patterns; anything else 404s.
    # send_from_directory rejects ".." so no path traversal is possible.
    is_google = filename.startswith("google") and filename.endswith(".html")
    is_bing   = filename == "BingSiteAuth.xml"
    if not (is_google or is_bing):
        abort(404)
    mime = "application/xml" if is_bing else "text/html"
    return send_from_directory(WEBAPP_DIR, filename, mimetype=mime)


# @celery.task
# def divide(x, y):
#     import time

#     time.sleep(5)
#     return x / y
