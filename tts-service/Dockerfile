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

# Warm the model into the image layer cache (optional; speeds first request).
RUN python -c "from transformers import VitsModel, AutoTokenizer; \
    AutoTokenizer.from_pretrained('facebook/mms-tts-urd'); \
    VitsModel.from_pretrained('facebook/mms-tts-urd')" || true

EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
