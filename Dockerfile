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

# Threads help because requests spend time waiting on Azure; a longer timeout
# covers the OCR -> translate -> speech pipeline on large inputs.
CMD ["gunicorn", "wsgi:app", "--workers", "2", "--threads", "4", \
     "--timeout", "120", "--bind", "0.0.0.0:8080"]
