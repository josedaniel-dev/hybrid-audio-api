"""
Hybrid Audio API — Cache Router
v5.1 NDF-Sonic3 — Full Contract-Aware Cache Integration

Changes in v5.1:
    • Adds GCS bucket verification: /cache/check_in_bucket
    • Adds GCS bucket listing:      /cache/bucket_list
    • Compatibility map now includes:
          - has_signature
          - compatible (via is_entry_contract_compatible)
          - stored vs current contract fields
    • Extended mode exposes summary_extended() + full index
    • Fully backward-compatible (v3.x / v4.x safe)
"""

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Dict, Any

# ============================================================
# Cache Manager (v5.0 Sonic-3 contract-aware)
# ============================================================

try:
    from cache_manager import (
        summarize_cache,
        summary_extended,
        load_index,
        save_index,
        is_entry_contract_compatible,
    )
    CACHE_OK = True
except Exception:
    CACHE_OK = False

    def summarize_cache():
        return {"ok": False, "reason": "cache_manager unavailable"}

    def summary_extended():
        return {"ok": False, "reason": "extended summary unavailable"}

    def load_index():
        return {"stems": {}}

    def save_index(_):
        pass

    def is_entry_contract_compatible(_):
        return False


# ============================================================
# Batch Engine (unchanged)
# ============================================================

try:
    from batch_generate_stems import generate_rotational_stems
    BATCH_OK = True
except Exception:
    BATCH_OK = False


# ============================================================
# Optional GCS integration
# ============================================================

try:
    from gcloud_storage import (
        gcs_check_file_exists,
        gcs_resolve_uri,
        list_bucket_contents,
    )
    from config import is_gcs_enabled, GCS_FOLDER_STEMS, GCS_FOLDER_OUTPUTS
except Exception:
    gcs_check_file_exists = None
    gcs_resolve_uri = None
    list_bucket_contents = None

    def is_gcs_enabled():
        return False

    GCS_FOLDER_STEMS = "stems"
    GCS_FOLDER_OUTPUTS = "outputs"


router = APIRouter()


# ============================================================
# GET /cache/list
# ============================================================

@router.get("/list")
async def cache_list(extended: bool = Query(False)):
    """
    Returns:
        • Base or extended cache summary
        • Full stems index
        • Compatibility report (signature-based)
    """
    try:
        summary = summary_extended() if extended else summarize_cache()
        index = load_index()
        stems = index.get("stems", {})

        compat_map = {}

        for name, entry in stems.items():
            stored_fmt = entry.get("audio_format")
            stored_enc = entry.get("encoding")
            stored_ver = entry.get("cartesia_version")

            compat_map[name] = {
                "has_signature": bool(entry.get("contract_signature")),
                "compatible": bool(is_entry_contract_compatible(entry)),
                "stored_audio_format": stored_fmt,
                "stored_encoding": stored_enc,
                "stored_cartesia_version": stored_ver,
            }

        return {
            "status": "ok" if CACHE_OK else "warning",
            "cache_engine": CACHE_OK,
            "extended": extended,
            "summary": summary,
            "stems_count": len(stems),
            "stems": stems,
            "compatibility": compat_map,
        }

    except Exception as e:
        raise HTTPException(500, f"cache_list failed: {e}")


# ============================================================
# POST /cache/invalidate
# ============================================================

@router.post("/invalidate")
async def cache_invalidate(payload: Dict[str, Any]):
    """
    Removes a stem entry from the cache index.
    Body:
        { "stem_name": "stem.name.john" }
    """
    stem_name = payload.get("stem_name")
    if not stem_name:
        raise HTTPException(400, "Missing required field: stem_name")

    if not CACHE_OK:
        raise HTTPException(503, "cache_manager unavailable")

    try:
        index = load_index()
        stems = index.get("stems", {})

        if stem_name not in stems:
            return {
                "status": "not_found",
                "cache_engine": True,
                "stem": stem_name,
            }

        del stems[stem_name]
        index["stems"] = stems
        save_index(index)

        return {
            "status": "ok",
            "cache_engine": True,
            "removed": stem_name,
        }

    except Exception as e:
        raise HTTPException(500, f"cache_invalidate failed: {e}")


# ============================================================
# POST /cache/bulk_generate
# ============================================================

@router.post("/bulk_generate")
async def cache_bulk_generate(payload: Dict[str, str]):
    """
    Runs batch_generate_stems in rotational mode.

    Body:
        {
            "names_path": "data/common_names.json",
            "developers_path": "data/developer_names.json"
        }
    """
    names_path = payload.get("names_path")
    devs_path = payload.get("developers_path")

    if not names_path or not devs_path:
        raise HTTPException(400, "names_path and developers_path are required")

    if not BATCH_OK:
        raise HTTPException(503, "batch_generate_stems unavailable")

    try:
        np = Path(names_path)
        dp = Path(devs_path)

        if not np.exists():
            raise HTTPException(400, f"Names dataset not found: {np}")

        if not dp.exists():
            raise HTTPException(400, f"Developers dataset not found: {dp}")

        generate_rotational_stems(np, dp)

        return {
            "status": "ok",
            "batch_engine": True,
            "processed": {
                "names": str(np),
                "developers": str(dp),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"bulk_generate failed: {e}")


# ============================================================
# NEW v5.1 — Bucket Stem Verification
# ============================================================

@router.get("/check_in_bucket")
async def cache_check_in_bucket(label: str):
    """
    Check whether a cached stem also exists in GCS.
    Looks for: stems/<label>.wav
    """
    if not (is_gcs_enabled() and gcs_check_file_exists):
        raise HTTPException(503, "GCS integration unavailable.")

    filename = f"{label}.wav"
    uri = f"{GCS_FOLDER_STEMS}/{filename}"

    exists = gcs_check_file_exists(uri)
    return {
        "status": "ok",
        "label": label,
        "exists": exists,
        "gcs_uri": gcs_resolve_uri(uri) if exists else None,
    }


# ============================================================
# NEW v5.1 — Bucket Listing
# ============================================================

@router.get("/bucket_list")
async def cache_bucket_list(prefix: str = ""):
    """
    List bucket contents for audit purposes.
    Requires GCS enabled.
    """
    if not (is_gcs_enabled() and list_bucket_contents):
        raise HTTPException(503, "GCS integration unavailable.")

    try:
        contents = list_bucket_contents(prefix=prefix)
        return {
            "status": "ok",
            "prefix": prefix,
            "count": len(contents),
            "items": contents,
        }
    except Exception as e:
        raise HTTPException(500, f"bucket_list failed: {e}")
