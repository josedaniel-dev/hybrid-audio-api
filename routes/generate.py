from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, Dict, Any, List

"""
routes/generate.py — v5.0 NDF Sonic-3 Contract
Unified Stem Generator (Name / Developer / Combined)

v5.0 features:
    • Correct stem labels from config:
          stem.name.<slug>
          stem.developer.<slug>
    • Fully Sonic-3 aligned (delegates entirely to cartesia_generate)
    • Cache-aware (v5.0 contract signature support)
    • GCS upload + verification using correct v5.0 helpers
    • extended=true returns full metadata for UI/CLI integration
"""

# Core Sonic-3 pipeline
try:
    from assemble_message import cartesia_generate, _clean_text_from_stem
    from cache_manager import get_cached_stem, load_index
    from config import (
        VOICE_ID,
        stem_label_name,
        stem_label_developer,
        GCS_FOLDER_STEMS,
        GCS_FOLDER_OUTPUTS,
        is_gcs_enabled,
    )
    CARTESIA_AVAILABLE = True
except Exception:
    CARTESIA_AVAILABLE = False

# Optional rotational engine
try:
    from rotational_engine import get_next_name, get_next_developer
    ROTATION_ENGINE_AVAILABLE = True
except Exception:
    ROTATION_ENGINE_AVAILABLE = False

# Optional GCS helpers (correct ones)
try:
    from gcloud_storage import (
        upload_stem_file,
        list_bucket_contents,
        resolve_gcs_blob_name,
    )
except Exception:
    upload_stem_file = None
    list_bucket_contents = None
    resolve_gcs_blob_name = None


router = APIRouter()


# =============================================================================
# Models
# =============================================================================

class NameRequest(BaseModel):
    name: str
    voice_id: Optional[str] = None


class DeveloperRequest(BaseModel):
    developer: str
    voice_id: Optional[str] = None


class CombinedRequest(BaseModel):
    name: str
    developer: str
    voice_id: Optional[str] = None


# =============================================================================
# Helpers
# =============================================================================

def _norm(x: str) -> str:
    return x.strip().title()


# =============================================================================
# POST /generate/name
# =============================================================================

@router.post("/name")
async def generate_name(req: NameRequest, extended: bool = Query(False)):
    if not CARTESIA_AVAILABLE:
        raise HTTPException(503, "Cartesia engine unavailable")

    name = _norm(req.name)
    voice_id = req.voice_id or VOICE_ID

    label = stem_label_name(name)

    # Cache lookup
    cached = get_cached_stem(label)
    if cached:
        if extended:
            idx = load_index()["stems"].get(label)
            return {
                "status": "cached",
                "label": label,
                "text": name,
                "natural_text": name,
                "path": cached,
                "cache_entry": idx,
            }
        return {"status": "cached", "label": label, "path": cached}

    # Generate via Sonic-3
    try:
        path = cartesia_generate(name, label, voice_id=voice_id)
        resp = {
            "status": "generated",
            "label": label,
            "text": name,
            "path": path,
        }

        # Upload to GCS if enabled
        if is_gcs_enabled() and upload_stem_file:
            resp["gcs"] = upload_stem_file(path)

        if extended:
            resp["natural_text"] = _clean_text_from_stem(label)
            resp["cache_entry"] = load_index()["stems"].get(label)

        return resp

    except Exception as e:
        raise HTTPException(500, f"Failed to generate name stem: {e}")


# =============================================================================
# POST /generate/developer
# =============================================================================

@router.post("/developer")
async def generate_developer(req: DeveloperRequest, extended: bool = Query(False)):
    if not CARTESIA_AVAILABLE:
        raise HTTPException(503, "Cartesia engine unavailable")

    dev = _norm(req.developer)
    voice_id = req.voice_id or VOICE_ID

    label = stem_label_developer(dev)

    cached = get_cached_stem(label)
    if cached:
        if extended:
            return {
                "status": "cached",
                "label": label,
                "text": dev,
                "natural_text": dev,
                "path": cached,
                "cache_entry": load_index()["stems"].get(label),
            }
        return {"status": "cached", "label": label, "path": cached}

    try:
        path = cartesia_generate(dev, label, voice_id=voice_id)
        resp = {
            "status": "generated",
            "label": label,
            "text": dev,
            "path": path,
        }

        if is_gcs_enabled() and upload_stem_file:
            resp["gcs"] = upload_stem_file(path)

        if extended:
            resp["natural_text"] = _clean_text_from_stem(label)
            resp["cache_entry"] = load_index()["stems"].get(label)

        return resp

    except Exception as e:
        raise HTTPException(500, f"Failed to generate developer stem: {e}")


# =============================================================================
# POST /generate/combined
# =============================================================================

@router.post("/combined")
async def generate_combined(req: CombinedRequest, extended: bool = Query(False)):
    if not CARTESIA_AVAILABLE:
        raise HTTPException(503, "Cartesia engine unavailable")

    name = _norm(req.name)
    dev = _norm(req.developer)
    voice_id = req.voice_id or VOICE_ID

    name_label = stem_label_name(name)
    dev_label = stem_label_developer(dev)

    # Name path (cached or generate)
    n_cached = get_cached_stem(name_label)
    n_path = n_cached or cartesia_generate(name, name_label, voice_id=voice_id)

    # Developer path
    d_cached = get_cached_stem(dev_label)
    d_path = d_cached or cartesia_generate(dev, dev_label, voice_id=voice_id)

    result = {
        "status": "ok",
        "name": {"label": name_label, "path": n_path},
        "developer": {"label": dev_label, "path": d_path},
        "pair": {"name": name, "developer": dev},
        "voice_id": voice_id,
    }

    if extended:
        idx = load_index()["stems"]
        result["name"]["cache_entry"] = idx.get(name_label)
        result["developer"]["cache_entry"] = idx.get(dev_label)

    return result


# =============================================================================
# 🔥 Bucket Verification (correct v5.0 design)
# =============================================================================

@router.get("/check/stem_in_bucket")
async def check_stem_in_bucket(label: str):
    """
    Correct GCS check:
        we list bucket contents with prefix = stems/<label>
    """

    if not (list_bucket_contents and is_gcs_enabled()):
        raise HTTPException(503, "GCS integration unavailable")

    prefix = f"{GCS_FOLDER_STEMS}/{label}"
    blobs = list_bucket_contents(prefix=prefix)
    exists = any(prefix in b for b in blobs)

    return {"status": "ok", "label": label, "exists": exists}


@router.get("/check/stem_path")
async def check_stem_path(label: str):
    """Return the full local + GCS path metadata."""
    idx = load_index()["stems"].get(label)
    if not idx:
        return {"status": "not_found", "label": label}

    local_path = idx["path"]

    gcs_uri = None
    if list_bucket_contents and is_gcs_enabled():
        prefix = f"{GCS_FOLDER_STEMS}/{label}"
        blobs = list_bucket_contents(prefix=prefix)
        if blobs:
            gcs_uri = f"https://storage.googleapis.com/{resolve_gcs_blob_name(prefix, None)}"

    return {
        "status": "ok",
        "label": label,
        "local_path": local_path,
        "gcs_path": gcs_uri,
        "metadata": idx,
    }


# =============================================================================
# UI/CLI Presets
# =============================================================================

@router.get("/preset_names")
async def preset_names():
    try:
        from config import COMMON_NAMES_FILE
        import json
        data = json.loads(Path(COMMON_NAMES_FILE).read_text())
        return {"status": "ok", "items": sorted(data.get("items", []))}
    except Exception as e:
        raise HTTPException(500, f"Cannot load names dataset: {e}")


@router.get("/preset_developers")
async def preset_developers():
    try:
        from config import DEVELOPER_NAMES_FILE
        import json
        data = json.loads(Path(DEVELOPER_NAMES_FILE).read_text())
        return {"status": "ok", "items": sorted(data.get("items", []))}
    except Exception as e:
        raise HTTPException(500, f"Cannot load developers dataset: {e}")
