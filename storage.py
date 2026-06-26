"""
Storage backend: local filesystem (dev) or Backblaze B2 (prod).

When S3_BUCKET is set, files are uploaded to B2 via boto3's S3-compatible
API and served via direct B2 URLs. Render never touches the file bytes
after upload, so it burns no bandwidth serving audio or documents.

Requires the B2 bucket to be set to *public* in the Backblaze console so
browsers can fetch audio directly without auth headers.

Env (all required when S3_BUCKET is set):
  S3_BUCKET            bucket name, e.g. eyewaz-voicebank
  S3_ENDPOINT          e.g. https://s3.us-west-004.backblazeb2.com
  S3_REGION            e.g. us-west-004
  S3_ACCESS_KEY_ID     B2 application key ID
  S3_SECRET_ACCESS_KEY B2 application key
"""

import os
import uuid

from werkzeug.utils import secure_filename

# ── Local mode ────────────────────────────────────────────────────────────────

UPLOAD_DIR = os.getenv("STORAGE_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── B2 / S3 client (lazy singleton) ──────────────────────────────────────────

_s3_client = None


def _cloud_enabled():
    return bool(os.getenv("S3_BUCKET"))


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT"),
            region_name=os.getenv("S3_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        )
    return _s3_client


def _bucket():
    return os.getenv("S3_BUCKET")


def _b2_public_url(blob_name):
    endpoint = os.getenv("S3_ENDPOINT", "").rstrip("/")
    return f"{endpoint}/{_bucket()}/{blob_name}"


# ── Shared types ──────────────────────────────────────────────────────────────

class _Downloadable:
    """Lazily reads file bytes, mirroring Azure's StorageStreamDownloader."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    readall = read


class StoredFile:
    """A persisted file, shaped like an Azure BlobClient for call-site compat."""

    def __init__(self, blob_name, *, path=None, cloud_url=None):
        self.blob_name = blob_name
        self.name = blob_name
        self.path = path
        self._cloud_url = cloud_url

    @property
    def url(self):
        if self._cloud_url:
            return self._cloud_url
        return f"/files/{self.blob_name}"

    def read_bytes(self):
        if self._cloud_url:
            resp = _s3().get_object(Bucket=_bucket(), Key=self.blob_name)
            return resp["Body"].read()
        with open(self.path, "rb") as fh:
            return fh.read()

    def download_blob(self):
        return _Downloadable(self.read_bytes())


# ── Public API ────────────────────────────────────────────────────────────────

def _to_bytes(file):
    """Accept a werkzeug FileStorage, a file-like object, or raw bytes."""
    if isinstance(file, (bytes, bytearray)):
        return bytes(file)
    if hasattr(file, "read"):
        try:
            file.seek(0)
        except (OSError, ValueError):
            pass
        return file.read()
    raise TypeError(f"Unsupported file type for storage: {type(file)!r}")


def _content_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
        "pdf": "application/pdf",
        "png": "image/png", "jpg": "image/jpeg",
        "jpeg": "image/jpeg", "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def save_file(file, filename):
    """Persist *file* and return a :class:`StoredFile`.

    Uploads to B2 when S3_BUCKET is configured, otherwise writes to
    the local uploads/ directory.
    """
    safe = secure_filename(filename) or "file"
    blob_name = f"{uuid.uuid4().hex[:8]}_{safe}"
    data = _to_bytes(file)

    if _cloud_enabled():
        _s3().put_object(
            Bucket=_bucket(),
            Key=blob_name,
            Body=data,
            ContentType=_content_type(filename),
        )
        return StoredFile(blob_name, cloud_url=_b2_public_url(blob_name))

    dest = os.path.join(UPLOAD_DIR, blob_name)
    with open(dest, "wb") as fh:
        fh.write(data)
    return StoredFile(blob_name, path=dest)


def delete_file(blob_name):
    """Remove a stored file. Returns True if the operation succeeded."""
    if _cloud_enabled():
        try:
            _s3().delete_object(Bucket=_bucket(), Key=blob_name)
            return True
        except Exception:
            return False

    path = os.path.join(UPLOAD_DIR, secure_filename(blob_name))
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
