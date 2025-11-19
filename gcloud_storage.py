"""
gcloud_storage.py — Hybrid Audio API
──────────────────────────────────────────────────────────────
v3.6 NDF-004 — Introduce optional Google Cloud Storage integration

v3.9.1 NDF-040 — Additive Rotational Path Support
• Adds resolver for new structured stems:
      stems/name/<NAME>/<NAME>_timestamp.wav
      stems/developer/<DEV>/<DEV>_timestamp.wav
• Adds upload_stem_file() and upload_output_file() wrappers
• Does not modify existing upload_to_gcs() behavior
Author: José Daniel Soto
"""

import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# External dependency — Google Cloud Storage SDK
try:
    from google.cloud import storage
    from google.api_core import exceptions as gcs_exceptions
except ImportError:
    storage = None
    gcs_exceptions = None

# Internal config reference
from config import (
    GCS_BUCKET,
    GCS_FOLDER_OUTPUTS,
    GCS_FOLDER_STEMS,
    GOOGLE_APPLICATION_CREDENTIALS,
    URL_BASE_GCS,
    PUBLIC_ACCESS,
    is_gcs_enabled,
)

# ────────────────────────────────────────────────
# v3.6 NDF-010 ADDITIVE — Import audit logger (non-destructive)
# ────────────────────────────────────────────────
try:
    from gcs_audit import log_gcs_audit
except Exception:
    def log_gcs_audit(*args, **kwargs):
        return False


# ────────────────────────────────────────────────
# 🧠 v3.6 NDF-004 — Safe Client Initialization
# ────────────────────────────────────────────────
def init_gcs_client() -> Optional["storage.Client"]:
    if not is_gcs_enabled():
        print("⚠️  GCS disabled or credentials missing — operating in local-only mode.")
        return None

    if storage is None:
        print("⚠️  google-cloud-storage package not installed — skipping upload.")
        return None

    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(GOOGLE_APPLICATION_CREDENTIALS).expanduser())
        client = storage.Client()
        return client
    except Exception as e:
        print(f"⚠️  Failed to initialize GCS client: {e}")
        return None


# ────────────────────────────────────────────────
# 🔏 v3.6 NDF-007 — Signed URL Support (UBLA-safe)
# ────────────────────────────────────────────────
def generate_signed_url(blob, expiration_seconds: int = 86400) -> Optional[str]:
    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="GET",
        )
    except Exception as e:
        print(f"⚠️  Failed to generate signed URL: {e}")
        return None


# ────────────────────────────────────────────────
# v3.9.1 NDF-040 — NEW: Blob name resolver for new stem/output structure
# ────────────────────────────────────────────────
def resolve_gcs_blob_name(local_path: str, folder: Optional[str] = None) -> str:
    """
    Additive helper:
        Converts local file like:
            stems/name/Luis/Luis_20251114_132244.wav
        Into a GCS blob name:
            stems/name/Luis/Luis_20251114_132244.wav

    Preserves folder= override (e.g., outputs/ or stems/)
    """
    p = Path(local_path)
    if folder:
        return f"{folder}/{p.name}"
    return str(local_path).replace("\\", "/")


# ────────────────────────────────────────────────
# ☁️ v3.6 NDF-004/007 — Upload Helper (UBLA Safe)
# (Unmodified — preserved exactly)
# ────────────────────────────────────────────────
def upload_to_gcs(local_file: str, folder: str = GCS_FOLDER_OUTPUTS) -> Dict[str, Any]:
    file_path = Path(local_file)
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: {local_file}"}

    if not is_gcs_enabled():
        return {
            "ok": False,
            "mode": "local-only",
            "message": "GCS not enabled — returning local path only.",
            "file_path": str(file_path),
        }

    client = init_gcs_client()
    if client is None:
        return {
            "ok": False,
            "mode": "local-only",
            "message": "GCS client unavailable.",
            "file_path": str(file_path),
        }

    try:
        t0 = time.time()
        bucket = client.bucket(GCS_BUCKET)

        # NEW: use resolver for structured paths
        blob_name = resolve_gcs_blob_name(str(file_path), folder=folder)
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(str(file_path))

        signed_url = generate_signed_url(blob, expiration_seconds=86400)
        latency = round(time.time() - t0, 3)

        metadata = {
            "ok": True,
            "bucket": GCS_BUCKET,
            "blob_name": blob_name,
            "size_bytes": file_path.stat().st_size,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latency_sec": latency,
            "public_access": PUBLIC_ACCESS,
            "signed_url": signed_url,
            "file_url": signed_url or f"{URL_BASE_GCS}/{blob_name}",
        }

        try:
            log_gcs_audit(metadata)
        except Exception:
            pass

        return metadata

    except gcs_exceptions.NotFound:
        return {"ok": False, "error": f"Bucket not found: {GCS_BUCKET}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}
# ────────────────────────────────────────────────
# v3.9.1 NDF-041 — NEW: Upload wrapper for stem files
# ────────────────────────────────────────────────
def upload_stem_file(stem_path: str) -> Dict[str, Any]:
    """
    Additive wrapper:
        Always uploads stems to GCS_FOLDER_STEMS.
    Does not replace existing upload_to_gcs().
    """
    return upload_to_gcs(stem_path, folder=GCS_FOLDER_STEMS)


# ────────────────────────────────────────────────
# v3.9.1 NDF-042 — NEW: Upload wrapper for final output files
# ────────────────────────────────────────────────
def upload_output_file(output_path: str) -> Dict[str, Any]:
    """
    Additive wrapper:
        Always uploads final assembled files to GCS_FOLDER_OUTPUTS.
    """
    return upload_to_gcs(output_path, folder=GCS_FOLDER_OUTPUTS)


# ────────────────────────────────────────────────
# 🩺 v3.6 NDF-005 — Health Check Utility
# (Unmodified — preserved exactly)
# ────────────────────────────────────────────────
def gcs_healthcheck() -> Dict[str, Any]:
    if not is_gcs_enabled() or storage is None:
        return {"ok": False, "enabled": False, "reason": "GCS disabled or client missing"}

    try:
        t0 = time.time()
        client = init_gcs_client()
        if client is None:
            return {"ok": False, "enabled": False, "reason": "Client init failed"}

        bucket = client.bucket(GCS_BUCKET)
        exists = bucket.exists()
        latency = round(time.time() - t0, 3)
        return {
            "ok": bool(exists),
            "enabled": True,
            "bucket": GCS_BUCKET,
            "mode": "private" if PUBLIC_ACCESS else "restricted",
            "latency_sec": latency,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    except Exception as e:
        return {
            "ok": False,
            "enabled": True,
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


# ────────────────────────────────────────────────
# 🧪 Diagnostic Mode (unchanged)
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    test_file = sys.argv[1] if len(sys.argv) > 1 else None

    print("🧩 Hybrid Audio GCS Diagnostic (v3.6 NDF-004 + 007 + 3.9.1 Extensions)")
    print("─────────────────────────────────────────────")
    print(f"GCS Enabled: {is_gcs_enabled()}")
    print(f"Bucket: {GCS_BUCKET or '—'}")
    print(f"Credentials: {GOOGLE_APPLICATION_CREDENTIALS or '—'}")
    print(f"Public Access: {PUBLIC_ACCESS}")
    print("─────────────────────────────────────────────")

    print("Healthcheck →", gcs_healthcheck())

    if test_file:
        print(f"\nAttempting upload of {test_file}...")
        result = upload_to_gcs(test_file)
        print(result)
    else:
        print("ℹ️  Pass a file path to test upload.")
