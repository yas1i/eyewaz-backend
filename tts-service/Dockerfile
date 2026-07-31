FROM python:3.11-slim

# libsndfile is only for the optional MMS fallback path; piper does not need it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py normalize_urdu.py voices.py ./

# The trained voices are NOT baked in: they are large binaries and the repo is
# public. Mount them instead, e.g. -v /opt/eyewaz-tts/voices:/srv/voices
ENV VOICES_DIR=/srv/voices

EXPOSE 8090
# Shell form so the host's $PORT is honoured (falls back to 8090 locally).
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8090}
