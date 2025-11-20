"""Helpers for comparing local stems against GCS copies."""

from __future__ import annotations

from pathlib import Path

from config import STEMS_DIR, GCS_BUCKET, GCS_FOLDER_STEMS, is_gcs_enabled, build_gcs_blob_path

try:
    from gcloud_storage import init_gcs_client
except Exception:  # pragma: no cover - optional dependency
    init_gcs_client = None  # type: ignore


def local_has_file(stem_filename: str) -> bool:
    return (STEMS_DIR / stem_filename).exists()


def gcs_has_file(stem_filename: str) -> bool:
    if not (is_gcs_enabled() and init_gcs_client and GCS_BUCKET):
        return False
    try:
        client = init_gcs_client()
        if not client:
            return False
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(build_gcs_blob_path(GCS_FOLDER_STEMS, stem_filename))
        return blob.exists()
    except Exception:
        return False


def compare_local_vs_gcs(stem_filename: str) -> str:
    """Return a high-level consistency status for a given stem filename."""

    local = local_has_file(stem_filename)
    gcs = gcs_has_file(stem_filename)

    if local and gcs:
        return "match"
    if local and not gcs:
        return "local_only"
    if gcs and not local:
        return "gcs_only"
    return "missing"


__all__ = ["compare_local_vs_gcs", "gcs_has_file", "local_has_file"]
