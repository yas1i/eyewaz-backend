"""
Local filesystem storage backend.

Replaces the original Azure Blob Storage dependency. Files (uploaded
documents/images and generated audio) are written under ``uploads/`` and
served by Flask at ``/files/<name>`` (see ``server.py``).

The returned :class:`StoredFile` mimics the small slice of the Azure
``BlobClient`` interface the rest of the codebase relied on
(``.url``, ``.blob_name`` and ``.download_blob()``), so call sites did not
need to change their shape.
"""

import io
import os
import uuid

from werkzeug.utils import secure_filename

# Where uploaded files + generated audio are stored. Defaults to uploads/ next
# to this module; in production set STORAGE_DIR to a persistent path
# (e.g. /home/uploads on Azure App Service).
UPLOAD_DIR = os.getenv("STORAGE_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "uploads"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Base URL the audio/file links are reachable at. For the iOS simulator
# "localhost" works; for a physical device set PUBLIC_BASE_URL to the LAN IP
# (e.g. http://192.168.1.133:4242) or the deployed host.
def _public_base_url():
    return os.getenv("PUBLIC_BASE_URL", "http://localhost:4242").rstrip("/")


class _Downloadable:
    """Lazily reads file bytes, mirroring Azure's StorageStreamDownloader."""

    def __init__(self, path):
        self._path = path

    def read(self):
        with open(self._path, "rb") as fh:
            return fh.read()

    # Azure's downloader exposes readall(); keep it for parity.
    readall = read


class StoredFile:
    """A file persisted on the local disk, shaped like an Azure BlobClient."""

    def __init__(self, blob_name, path):
        self.blob_name = blob_name
        self.name = blob_name
        self.path = path

    @property
    def url(self):
        return f"{_public_base_url()}/files/{self.blob_name}"

    def read_bytes(self):
        with open(self.path, "rb") as fh:
            return fh.read()

    def download_blob(self):
        return _Downloadable(self.path)


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


def save_file(file, filename):
    """Persist ``file`` under ``uploads/`` and return a :class:`StoredFile`.

    A short uuid prefix keeps filenames unique so concurrent uploads with the
    same name do not clobber each other.
    """
    safe = secure_filename(filename) or "file"
    blob_name = f"{uuid.uuid4().hex[:8]}_{safe}"
    dest = os.path.join(UPLOAD_DIR, blob_name)
    with open(dest, "wb") as fh:
        fh.write(_to_bytes(file))
    return StoredFile(blob_name, dest)


def delete_file(blob_name):
    """Remove a stored file. Returns True if it existed."""
    path = os.path.join(UPLOAD_DIR, secure_filename(blob_name))
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
