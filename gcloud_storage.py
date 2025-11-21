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


# ───────────────────────────────────────────────────────────────
# 🛡️ HARDENED: Sanitización mínima de paths
# ───────────────────────────────────────────────────────────────
def _sanitize_filename(filename: str) -> str:
    """Previene directory traversal y caracteres ilegales."""
    name = os.path.basename(filename)
    return name.replace("..", "").replace("\\", "/").strip()


def _sanitize_folder(folder: str) -> str:
    folder = folder.strip().replace("..", "").replace("\\", "/")
    return folder.rstrip("/")


# ───────────────────────────────────────────────────────────────
# 🧠 GCS client initialization
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
        return None


# ───────────────────────────────────────────────────────────────
# 🔏 Signed URL
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
        return None


# ───────────────────────────────────────────────────────────────
# 📦 Hardened blob-path resolver
# ───────────────────────────────────────────────────────────────
def resolve_gcs_blob_name(local_path: str, folder: Optional[str] = None) -> str:
    """
    Securely maps a local path -> GCS blob path.

    v5.3 NDF Additive Upgrade:
    -----------------------------------
    • If the file lives under a structured stems directory:
         stems/name/<NAME>/file.wav
         stems/developer/<DEV>/file.wav
         stems/script/<SCRIPT>/file.wav
      → Preserve the entire relative path in GCS.

    • Else: fallback to classic behavior:
         <folder>/<filename>

    • Always sanitize both folder and filename.
    """
    p = Path(local_path)

    # Detect if inside our structured stems hierarchy
    try:
        parts = p.parts
        # Find "stems" in the path
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
# ☁️ Hardened uploader
# ───────────────────────────────────────────────────────────────
def upload_to_gcs(local_file: str, folder: str = GCS_FOLDER_OUTPUTS) -> Dict[str, Any]:
    file_path = Path(local_file)

    # Local existence check
    if not file_path.exists() or not file_path.is_file():
        return {"ok": False, "error": f"File not found: {local_file}"}

    # GCS disabled
    if not is_gcs_enabled():
        return {
            "ok": False,
            "mode": "local-only",
            "file_path": str(file_path),
            "reason": "GCS disabled",
        }

    # Client init
    client = init_gcs_client()
    if client is None:
        return {
            "ok": False,
            "mode": "local-only",
            "file_path": str(file_path),
            "reason": "GCS client unavailable",
        }

    if not GCS_BUCKET:
        return {"ok": False, "error": "GCS_BUCKET not configured"}

    try:
        t0 = time.time()
        bucket = client.bucket(GCS_BUCKET)

        if not bucket.exists():
            return {"ok": False, "error": f"Bucket not found: {GCS_BUCKET}"}

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
        except Exception:
            pass

        return metadata

    except gcs_exceptions.NotFound:
        return {"ok": False, "error": f"Bucket not found: {GCS_BUCKET}"}

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ───────────────────────────────────────────────────────────────
# Convenience wrappers (unchanged except hardened resolver)
# ───────────────────────────────────────────────────────────────
def upload_stem_file(stem_path: str) -> Dict[str, Any]:
    return upload_to_gcs(stem_path, folder=GCS_FOLDER_STEMS)


def upload_output_file(output_path: str) -> Dict[str, Any]:
    return upload_to_gcs(output_path, folder=GCS_FOLDER_OUTPUTS)


# ───────────────────────────────────────────────────────────────
# 🩺 Health check (unchanged, but safer)
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
        return {
            "ok": False,
            "enabled": True,
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
# ───────────────────────────────────────────────────────────────
# v5.3 NDF — Minimal compatibility wrappers for tests + API
#    These functions are EXPECTED by:
#       - rotation.py  (/rotation/check_bucket)
#       - cache.py     (/cache/check_in_bucket)
#       - test_gcs_check_in_bucket.py
#    Additive-only: they DO NOT alter existing logic.
# ───────────────────────────────────────────────────────────────

def gcs_check_file_exists(blob_path: str) -> bool:
    """
    Minimal existence checker for internal + test use.

    Returns:
        True  → blob exists in GCS bucket
        False → missing OR GCS disabled OR SDK unavailable

    Fully NDF-safe and never raises.
    """
    try:
        client = init_gcs_client()
        if not client or not is_gcs_enabled() or not GCS_BUCKET:
            return False

        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(blob_path)
        return blob.exists()
    except Exception:
        return False


def gcs_resolve_uri(blob_path: str) -> str:
    """
    Build a public-style GCS URL for a blob.
    This is used by rotation.py + cache.py.
    """
    try:
        return f"{URL_BASE_GCS}/{blob_path}"
    except Exception:
        return blob_path
