FROM python:3.11-slim

# libsndfile is required by the `soundfile` package (audio duration).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Bind to the host-provided $PORT (Render/Railway/Fly set this); default 8080
# for Azure/local. Shell form so $PORT expands. Threads + long timeout cover the
# OCR -> translate -> speech pipeline.
CMD gunicorn wsgi:app --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT:-8080}
