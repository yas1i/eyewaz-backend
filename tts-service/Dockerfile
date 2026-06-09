FROM python:3.11-slim

# libsndfile for soundfile; build tools occasionally needed by deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
# CPU torch by default. For GPU, use an nvidia/cuda base + matching torch wheel.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Bake the model into the image (no || true — fail loudly if the id is wrong).
RUN python -c "from transformers import VitsModel, AutoTokenizer; \
    AutoTokenizer.from_pretrained('facebook/mms-tts-urd-script_arabic'); \
    VitsModel.from_pretrained('facebook/mms-tts-urd-script_arabic')"

EXPOSE 8090
# Shell form so Render's $PORT is honoured (falls back to 8090 locally).
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8090}
