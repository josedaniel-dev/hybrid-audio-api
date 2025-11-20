"""Integrity inspection routes for stems and outputs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException

from config import (
    STEMS_DIR,
    OUTPUT_DIR,
    GCS_BUCKET,
    GCS_FOLDER_STEMS,
    GCS_FOLDER_OUTPUTS,
    build_gcs_blob_path,
    build_gcs_uri,
    is_gcs_enabled,
)
from validator_audio import (
    validate_wav_header,
    validate_sample_rate,
    validate_channels,
    validate_encoding,
    validate_duration,
    validate_merge_integrity,
)

try:
    from gcloud_storage import init_gcs_client
except Exception:
    init_gcs_client = None  # type: ignore

router = APIRouter()


# Helpers --------------------------------------------------------------------

def _file_info(file_path: Path, folder: str) -> Dict[str, Any]:
    exists = file_path.exists()
    info: Dict[str, Any] = {
        "file": str(file_path),
        "exists": exists,
        "size_bytes": file_path.stat().st_size if exists else 0,
        "last_modified": datetime.utcfromtimestamp(file_path.stat().st_mtime).isoformat()
        if exists
        else None,
        "wav_header": {},
        "cache_status": "missing" if not exists else "present",
        "public_url": None,
        "signed_url": None,
    }

    if exists:
        header = validate_wav_header(str(file_path))
        validate_sample_rate(str(file_path))
        validate_channels(str(file_path))
        validate_encoding(str(file_path))
        validate_duration(str(file_path))
        validate_merge_integrity(str(file_path))
        info["wav_header"] = header

    if is_gcs_enabled() and GCS_BUCKET and init_gcs_client:
        blob_name = build_gcs_blob_path(folder, file_path.name)
        info["public_url"] = build_gcs_uri(folder, file_path.name)
        try:
            client = init_gcs_client()
            if client:
                bucket = client.bucket(GCS_BUCKET)
                blob = bucket.blob(blob_name)
                if blob.exists():
                    info["cache_status"] = "gcs"
                    info["signed_url"] = blob.generate_signed_url(expiration=3600)
        except Exception:
            pass

    return info


def _list_wavs(root: Path) -> List[Path]:
    return [p for p in root.glob("*.wav") if p.is_file()]


# Routes ---------------------------------------------------------------------


@router.get("/integrity/stems")
async def integrity_stems() -> Dict[str, Any]:
    """Return integrity metadata for all stems."""

    try:
        files = _list_wavs(STEMS_DIR)
        items = [_file_info(path, GCS_FOLDER_STEMS) for path in files]
        return {"status": "ok", "count": len(items), "items": items}
    except Exception as exc:
        raise HTTPException(500, f"Failed to inspect stems: {exc}")


@router.get("/integrity/outputs")
async def integrity_outputs() -> Dict[str, Any]:
    """Return integrity metadata for all rendered outputs."""

    try:
        files = _list_wavs(OUTPUT_DIR)
        items = [_file_info(path, GCS_FOLDER_OUTPUTS) for path in files]
        return {"status": "ok", "count": len(items), "items": items}
    except Exception as exc:
        raise HTTPException(500, f"Failed to inspect outputs: {exc}")


__all__ = ["router"]
