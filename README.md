# EYEWAZ Backend

Flask-RESTful API that helps blind and visually-impaired users: take a photo
of English text and hear it read aloud in **Urdu**.

**Pipeline:** image/document → Azure Vision OCR → English→Urdu translation
(Azure Translator) → Urdu speech, male & female (Azure Speech) → stored and
served, with per-user library, folders and favourites.

It also ships an **accessible web client** at `/app` so you can use the whole
flow from a browser (great with VoiceOver / TalkBack screen readers).

## Stack

- Flask-RESTful + MongoEngine (MongoDB)
- Azure AI services: Vision (OCR), Translator, Speech (TTS)
- Local filesystem storage (served at `/files/<name>`) — was Azure Blob
- JWT auth (Flask-JWT-Extended)

## Run locally

Prerequisites: Python 3.9+, a running MongoDB, and an Azure AI services key.

```bash
# 1. MongoDB (macOS, Homebrew)
brew tap mongodb/brew && brew install mongodb-community
brew services start mongodb/brew/mongodb-community

# 2. Python deps (libsndfile is needed by soundfile)
brew install libsndfile
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt

# 3. Config — copy the template and fill in your Azure key/region/endpoint
cp .env.example .env
#   ... edit .env ...

# 4. Run
./venv/bin/python app.py        # http://localhost:4242
```

Then open **http://localhost:4242/app** in a browser, create an account, and
upload a photo of English text to hear it in Urdu.

### Azure setup (one resource covers all three services)

Create a single **"Azure AI services"** multi-service resource in the Azure
portal, then put its **Key**, **Region** and **Endpoint** into `.env`
(`VISION_KEY` / `TRANSLATION_KEY` / `SPEECH_KEY` all use the same key). See
`.env.example` for the full list.

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/signup` | – | Create account |
| POST | `/api/login` | – | Login → JWT |
| POST | `/api/document-translation-and-speech` | JWT | Upload image/doc → OCR + Urdu + audio |
| GET  | `/api/document-translation-and-speech` | JWT | List the user's documents |
| DELETE | `/api/document` | JWT | Delete a document (`{"id": ...}`) |
| PUT  | `/api/fav-document` / `/api/unfav-document` | JWT | Favourite / unfavourite |
| PUT/POST | `/api/playback-time-record` | – | Save last-played time / bookmark |
| POST/GET/DELETE | `/api/folder` | JWT | Folder management |
| POST | `/api/files-folders` | JWT | Add documents to a folder |

Supported uploads: `jpg`, `png`, `jpeg` (OCR), plus `pdf`, `docx`, `txt`.

## Notes

- Secrets live in `.env` (gitignored). Never commit real keys.
- Uploaded files & generated audio are written to `uploads/` (gitignored) and
  served at `/files/<name>`. For physical devices or deployment, set
  `PUBLIC_BASE_URL` so those URLs are reachable.
