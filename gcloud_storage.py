#!/usr/bin/env python3
"""
gcloud_storage.py — Hybrid Audio API (HARDENED EDITION)
──────────────────────────────────────────────────────────────
v3.6 NDF-004 — Base GCS integration
v3.9.1 NDF-040 — Structured path + rotational support
v3.9.1-H1 — HARDENING LAYER
    • Sanitización estricta de paths
    • Validación de bucket / client antes de cada operación
    • Manejo detallado de errores (sin comprometer NDF)
    • Protección contra folder traversal
    • Hardened resolver + file guards
    • Upload wrappers reforzados
    • Logs menos verbosos en prod (respeta DEBUG)
Author: José Soto
"""

import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# Optional Google SDK
try:
    from google.cloud import storage
    from google.api_core import exceptions as gcs_exceptions
except ImportError:
    storage = None
    gcs_exceptions = None

# Internal config
from config import (
    GCS_BUCKET,
    GCS_FOLDER_OUTPUTS,
    GCS_FOLDER_STEMS,
    GOOGLE_APPLICATION_CREDENTIALS,
    URL_BASE_GCS,
    PUBLIC_ACCESS,
    DEBUG,
    is_gcs_enabled,
)

# Optional audit log
try:
    from gcs_audit import log_gcs_audit
except Exception:
    def log_gcs_audit(*args, **kwargs):
        return False

# Optional structured GCS logs
try:
    from observability.gcs_logs import log_gcs_event, log_gcs_error
except Exception:
    def log_gcs_event(*args, **kwargs):
        return None

    def log_gcs_error(*args, **kwargs):
        return None


# ───────────────────────────────────────────────────────────────
# Sanitized path helpers
# ───────────────────────────────────────────────────────────────
def _sanitize_filename(filename: str) -> str:
    """Prevent directory traversal and illegal characters in file names."""
    name = os.path.basename(filename)
    return name.replace("..", "").replace("\\", "/").strip()


def _sanitize_folder(folder: str) -> str:
    folder = folder.strip().replace("..", "").replace("\\", "/")
    return folder.rstrip("/")


# ───────────────────────────────────────────────────────────────
# GCS client initialization
# ───────────────────────────────────────────────────────────────
def init_gcs_client() -> Optional["storage.Client"]:
    if not is_gcs_enabled():
        if DEBUG:
            print("⚠️  GCS disabled or credentials missing — local mode only.")
        return None

    if storage is None:
        if DEBUG:
            print("⚠️  google-cloud-storage not installed.")
        return None

    try:
        cred_path = str(Path(GOOGLE_APPLICATION_CREDENTIALS).expanduser())
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
        return storage.Client()
    except Exception as e:
        if DEBUG:
            print(f"⚠️  Failed to init GCS client: {e}")
        log_gcs_error("init_gcs_client", str(e))
        return None


# ───────────────────────────────────────────────────────────────
# Signed URL
# ───────────────────────────────────────────────────────────────
def generate_signed_url(blob, expiration_seconds: int = 86400) -> Optional[str]:
    try:
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration_seconds),
            method="GET",
        )
    except Exception as e:
        if DEBUG:
            print(f"⚠️  Failed to generate signed URL: {e}")
        log_gcs_error("generate_signed_url", str(e))
        return None


# ───────────────────────────────────────────────────────────────
# Hardened blob-path resolver
# ───────────────────────────────────────────────────────────────
def resolve_gcs_blob_name(local_path: str, folder: Optional[str] = None) -> str:
    """
    Securely maps a local path -> GCS blob path.

    If the file lives under a structured stems directory:
         stems/name/<NAME>/file.wav
         stems/developer/<DEV>/file.wav
         stems/script/<SCRIPT>/file.wav
      → Preserve the entire relative path in GCS.

    Else: fallback to classic behavior:
         <folder>/<filename>

    Always sanitizes both folder and filename.
    """
    p = Path(local_path)

    # Detect structured stems hierarchy
    try:
        parts = p.parts
        if "stems" in parts:
            idx = parts.index("stems")
            relative = Path(*parts[idx:])  # stems/.../*.wav
            clean = _sanitize_folder(str(relative))
            return clean
    except Exception:
        pass

    # Classic fallback mode (legacy-compatible)
    filename = _sanitize_filename(local_path)
    folder = _sanitize_folder(folder) if folder else ""
    return f"{folder}/{filename}" if folder else filename


# ───────────────────────────────────────────────────────────────
# Uploader
# ───────────────────────────────────────────────────────────────
def upload_to_gcs(local_file: str, folder: str = GCS_FOLDER_OUTPUTS) -> Dict[str, Any]:
    file_path = Path(local_file)

    # Local existence check
    if not file_path.exists() or not file_path.is_file():
        msg = f"File not found: {local_file}"
        log_gcs_error("upload_to_gcs", msg)
        return {"ok": False, "error": msg}

    # GCS disabled
    if not is_gcs_enabled():
        payload = {
            "mode": "local-only",
            "file_path": str(file_path),
            "reason": "GCS disabled",
        }
        log_gcs_event("upload_skipped", payload)
        return {"ok": False, **payload}

    # Client init
    client = init_gcs_client()
    if client is None:
        payload = {
            "mode": "local-only",
            "file_path": str(file_path),
            "reason": "GCS client unavailable",
        }
        log_gcs_event("upload_skipped", payload)
        return {"ok": False, **payload}

    if not GCS_BUCKET:
        msg = "GCS_BUCKET not configured"
        log_gcs_error("upload_to_gcs", msg)
        return {"ok": False, "error": msg}

    try:
        t0 = time.time()
        bucket = client.bucket(GCS_BUCKET)

        if not bucket.exists():
            msg = f"Bucket not found: {GCS_BUCKET}"
            log_gcs_error("upload_to_gcs", msg)
            return {"ok": False, "error": msg}

        blob_name = resolve_gcs_blob_name(str(file_path), folder)
        blob = bucket.blob(blob_name)

        blob.upload_from_filename(str(file_path))

        signed_url = generate_signed_url(blob)
        latency = round(time.time() - t0, 3)

        metadata = {
            "ok": True,
            "bucket": GCS_BUCKET,
            "blob_name": blob_name,
            "size_bytes": file_path.stat().st_size,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latency_sec": latency,
            "public_access": PUBLIC_ACCESS,
            "file_url": signed_url or f"{URL_BASE_GCS}/{blob_name}",
            "signed_url": signed_url,
        }

        try:
            log_gcs_audit(metadata)
            log_gcs_event(
                "upload_success",
                {
                    "bucket": GCS_BUCKET,
                    "blob_name": blob_name,
                    "size_bytes": metadata["size_bytes"],
                    "latency_sec": latency,
                },
            )
        except Exception:
            pass

        return metadata

    except gcs_exceptions.NotFound:
        msg = f"Bucket not found: {GCS_BUCKET}"
        log_gcs_error("upload_to_gcs", msg)
        return {"ok": False, "error": msg}

    except Exception as e:
        log_gcs_error("upload_to_gcs", str(e))
        return {"ok": False, "error": str(e)}


# ───────────────────────────────────────────────────────────────
# Convenience wrappers
# ───────────────────────────────────────────────────────────────
def upload_stem_file(stem_path: str) -> Dict[str, Any]:
    return upload_to_gcs(stem_path, folder=GCS_FOLDER_STEMS)


def upload_output_file(output_path: str) -> Dict[str, Any]:
    return upload_to_gcs(output_path, folder=GCS_FOLDER_OUTPUTS)


# ───────────────────────────────────────────────────────────────
# Health check
# ───────────────────────────────────────────────────────────────
def gcs_healthcheck() -> Dict[str, Any]:
    if not is_gcs_enabled() or storage is None:
        return {"ok": False, "enabled": False, "reason": "GCS disabled or missing SDK"}

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
            "mode": "public" if PUBLIC_ACCESS else "restricted",
            "latency_sec": latency,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    except Exception as e:
        log_gcs_error("gcs_healthcheck", str(e))
        return {
            "ok": False,
            "enabled": True,
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


# ───────────────────────────────────────────────────────────────
# Minimal compatibility wrappers for tests + API (v1)
# ───────────────────────────────────────────────────────────────
def gcs_check_file_exists(blob_path: str) -> bool:
    """
    Minimal existence checker for internal + test use.

    Returns:
        True  → blob exists in GCS bucket
        False → missing OR GCS disabled OR SDK unavailable

    Never raises on error.
    """
    try:
        client = init_gcs_client()
        if not client or not is_gcs_enabled() or not GCS_BUCKET:
            return False

        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(blob_path)
        return blob.exists()
    except Exception as e:
        log_gcs_error("gcs_check_file_exists", str(e))
        return False


def gcs_resolve_uri(blob_path: str) -> str:
    """
    Build a public-style GCS URL for a blob.
    This is used by rotation and cache layers.
    """
    try:
        return f"{URL_BASE_GCS}/{blob_path}"
    except Exception:
        return blob_path


# ───────────────────────────────────────────────────────────────
# v2 API surface (explicit filename/blob operations)
# ───────────────────────────────────────────────────────────────
def _get_gcs_bucket():
    """
    Internal helper to get an initialized bucket instance.

    Returns:
        bucket object or None on failure.
    """
    try:
        if not is_gcs_enabled() or not GCS_BUCKET:
            return None

        client = init_gcs_client()
        if client is None:
            return None

        bucket = client.bucket(GCS_BUCKET)
        return bucket
    except Exception as e:
        log_gcs_error("_get_gcs_bucket", str(e))
        return None


def gcs_check_file_exists_v2(blob_path: str) -> bool:
    """
    Existence check for a GCS blob by its path.

    This function is intended for higher-level batch and consistency checks.
    It never raises and returns False on any failure or if GCS is disabled.
    """
    try:
        bucket = _get_gcs_bucket()
        if bucket is None:
            return False

        clean_blob = _sanitize_folder(blob_path)
        blob = bucket.blob(clean_blob)
        t0 = time.time()
        exists = blob.exists()
        latency = round(time.time() - t0, 3)

        log_gcs_event(
            "exists_check",
            {
                "blob_name": clean_blob,
                "exists": bool(exists),
                "latency_sec": latency,
            },
        )
        return bool(exists)
    except Exception as e:
        log_gcs_error("gcs_check_file_exists_v2", str(e))
        return False


def upload_file_v2(local_path: str, blob_path: str) -> Dict[str, Any]:
    """
    Upload a local file to an explicit GCS blob path.

    Args:
        local_path: Path to the local file.
        blob_path: Target blob path inside the bucket (e.g. "stems/name/...wav").

    Returns:
        Dict with keys:
            ok (bool)
            bucket (str, optional)
            blob_name (str, optional)
            local_path (str)
            size_bytes (int, optional)
            error (str, optional)
    """
    file_path = Path(local_path)

    if not file_path.exists() or not file_path.is_file():
        msg = f"File not found: {local_path}"
        log_gcs_error("upload_file_v2", msg)
        return {"ok": False, "local_path": str(file_path), "error": msg}

    bucket = _get_gcs_bucket()
    if bucket is None:
        payload = {
            "ok": False,
            "local_path": str(file_path),
            "reason": "GCS disabled or bucket unavailable",
        }
        log_gcs_event("upload_v2_skipped", payload)
        return payload

    try:
        clean_blob = _sanitize_folder(blob_path)
        blob = bucket.blob(clean_blob)

        t0 = time.time()
        blob.upload_from_filename(str(file_path))
        latency = round(time.time() - t0, 3)

        signed_url = generate_signed_url(blob)

        result = {
            "ok": True,
            "bucket": GCS_BUCKET,
            "blob_name": clean_blob,
            "local_path": str(file_path),
            "size_bytes": file_path.stat().st_size,
            "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latency_sec": latency,
            "file_url": signed_url or f"{URL_BASE_GCS}/{clean_blob}",
            "signed_url": signed_url,
        }

        log_gcs_event(
            "upload_v2_success",
            {
                "bucket": GCS_BUCKET,
                "blob_name": clean_blob,
                "size_bytes": result["size_bytes"],
                "latency_sec": latency,
            },
        )
        return result

    except Exception as e:
        msg = str(e)
        log_gcs_error("upload_file_v2", msg)
        return {
            "ok": False,
            "local_path": str(file_path),
            "blob_name": blob_path,
            "error": msg,
        }


def download_file_v2(blob_path: str, local_path: str) -> Dict[str, Any]:
    """
    Download a GCS blob into a local file.

    Args:
        blob_path: Path to the blob in the bucket.
        local_path: Local target path (directories will be created if missing).

    Returns:
        Dict with keys:
            ok (bool)
            bucket (str, optional)
            blob_name (str)
            local_path (str)
            size_bytes (int, optional)
            error (str, optional)
    """
    bucket = _get_gcs_bucket()
    if bucket is None:
        payload = {
            "ok": False,
            "blob_name": blob_path,
            "local_path": local_path,
            "reason": "GCS disabled or bucket unavailable",
        }
        log_gcs_event("download_v2_skipped", payload)
        return payload

    try:
        clean_blob = _sanitize_folder(blob_path)
        blob = bucket.blob(clean_blob)

        if not blob.exists():
            msg = f"Blob not found: {clean_blob}"
            log_gcs_error("download_file_v2", msg)
            return {
                "ok": False,
                "blob_name": clean_blob,
                "local_path": local_path,
                "error": msg,
            }

        local_path_obj = Path(local_path)
        local_path_obj.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.time()
        blob.download_to_filename(str(local_path_obj))
        latency = round(time.time() - t0, 3)

        size_bytes = local_path_obj.stat().st_size if local_path_obj.exists() else 0

        result = {
            "ok": True,
            "bucket": GCS_BUCKET,
            "blob_name": clean_blob,
            "local_path": str(local_path_obj),
            "size_bytes": size_bytes,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latency_sec": latency,
        }

        log_gcs_event(
            "download_v2_success",
            {
                "bucket": GCS_BUCKET,
                "blob_name": clean_blob,
                "size_bytes": size_bytes,
                "latency_sec": latency,
            },
        )
        return result

    except Exception as e:
        msg = str(e)
        log_gcs_error("download_file_v2", msg)
        return {
            "ok": False,
            "blob_name": blob_path,
            "local_path": local_path,
            "error": msg,
        }
