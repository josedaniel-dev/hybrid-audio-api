"""Integrity inspection routes for stems and outputs."""

from __future__ import annotations

import json
import struct
import wave
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
    STEMS_INDEX_FILE,
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
    compute_sha256,
    compute_rms,
    detect_clipped_samples,
)
from gcs_consistency import compare_local_vs_gcs

try:
    from gcloud_storage import init_gcs_client
except Exception:
    init_gcs_client = None  # type: ignore

router = APIRouter()


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _iter_samples(path: Path):
    """Iterate raw samples from WAV file in any 8/16/24/32-bit format."""
    with wave.open(str(path), "rb") as wf:
        sample_width = wf.getsampwidth()
        fmt_map = {1: "b", 2: "h", 4: "i"}  # 24-bit handled manually below

        while True:
            frames = wf.readframes(4096)
            if not frames:
                break

            count = len(frames) // sample_width

            if sample_width in fmt_map:
                samples = struct.unpack(f"<{count}{fmt_map[sample_width]}", frames)
                for sample in samples:
                    yield sample
            else:
                # Manual decode 24-bit
                for i in range(count):
                    chunk = frames[i * sample_width:(i + 1) * sample_width]
                    val = int.from_bytes(chunk, "little", signed=False)
                    if val & 0x800000:
                        val -= 0x1000000
                    yield val


def _peak_amplitude(path: Path) -> int:
    peak = 0
    for sample in _iter_samples(path):
        peak = max(peak, abs(sample))
    return peak


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
        "sha256": None,
        "peak_amplitude": None,
        "rms": None,
        "clipped_samples": None,
        "contract_compliance": False,
        "gcs_consistency": compare_local_vs_gcs(file_path.name),
    }

    if exists:
        try:
            header = validate_wav_header(str(file_path))
            validate_sample_rate(str(file_path))
            validate_channels(str(file_path))
            validate_encoding(str(file_path))
            validate_duration(str(file_path))
            validate_merge_integrity(str(file_path))

            info["wav_header"] = header
            info["contract_compliance"] = True
            info["sha256"] = compute_sha256(str(file_path))
            info["rms"] = compute_rms(str(file_path))
            info["clipped_samples"] = detect_clipped_samples(str(file_path))
            info["peak_amplitude"] = _peak_amplitude(file_path)

        except Exception as exc:
            info["wav_header"] = {"error": str(exc)}
            info["cache_status"] = "invalid"

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

        except Exception as exc:
            print(f"[WARN] Failed to resolve GCS info for {file_path.name}: {exc}")

    return info


def _list_wavs(root: Path) -> List[Path]:
    return [p for p in root.glob("*.wav") if p.is_file()]


def _load_stems_index() -> Dict[str, Any]:
    if not STEMS_INDEX_FILE.exists():
        return {}
    try:
        return json.loads(STEMS_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Failed to read stems_index.json: {exc}")


def _compare_index_to_fs(index: Dict[str, Any]) -> Dict[str, List[str]]:
    indexed = set(index.get("stems", {}).keys()) if index else set()
    present = {p.name for p in _list_wavs(STEMS_DIR)}

    return {
        "missing_in_fs": sorted(indexed - present),
        "missing_in_index": sorted(present - indexed),
    }


# -------------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------------

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


@router.get("/integrity/stems-index")
async def integrity_stems_index() -> Dict[str, Any]:
    """Return the recorded stems index and compare against filesystem."""
    index = _load_stems_index()
    comparison = _compare_index_to_fs(index)
    return {
        "status": "ok",
        "index_present": bool(index),
        "comparison": comparison,
        "index": index,
    }


__all__ = ["router"]
