from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any

"""
routes/rotation.py — v5.1 NDF Sonic-3 Contract
Rotational Name/Developer Stem Generator

Changes in v5.1:
    • Fixes label/schema mismatch (now mirrors assemble_message + cache_manager)
    • Labels are normalized to: stem.name.<name> / stem.developer.<dev>
    • Guarantees Sonic-3–compliant raw-text generation
    • Uses unified cache + index contract
    • Extended mode surfaces all internal metadata cleanly
    • Bucket verifier now uses centralized .env configuration
    • Zero breaking changes to rotational workflow
"""

# Core contracts
try:
    from assemble_message import cartesia_generate, _clean_text_from_stem
    from cache_manager import get_cached_stem, load_index
    from config import VOICE_ID, GCS_FOLDER_STEMS
    CARTESIA_AVAILABLE = True
except Exception:
    CARTESIA_AVAILABLE = False

# Rotational engine
try:
    from rotational_engine import (
        get_next_name,
        get_next_developer,
        get_next_pair,
    )
    ROTATION_ENGINE_AVAILABLE = True
except Exception:
    ROTATION_ENGINE_AVAILABLE = False

# Optional GCS support
try:
    from gcloud_storage import gcs_check_file_exists, gcs_resolve_uri
    from config import is_gcs_enabled
except Exception:
    gcs_check_file_exists = None
    gcs_resolve_uri = None

    def is_gcs_enabled():
        return False


router = APIRouter()

# =============================================================================
# Helpers
# =============================================================================

def _norm(text: str) -> str:
    return text.strip().lower().replace(" ", "_")


def _label_name(n: str) -> str:
    return f"stem.name.{_norm(n)}"


def _label_dev(d: str) -> str:
    return f"stem.developer.{_norm(d)}"


# =============================================================================
# v5.1 Request Model
# =============================================================================

class RotateGenerateRequest(BaseModel):
    voice_id: Optional[str] = None
    extended: Optional[bool] = False


# =============================================================================
# GET /rotation/next_name
# =============================================================================

@router.get("/next_name")
async def rotation_next_name():
    if not ROTATION_ENGINE_AVAILABLE:
        raise HTTPException(503, "Rotational engine unavailable.")

    name = get_next_name()
    if not name:
        raise HTTPException(500, "Rotation engine returned no name.")

    return {"status": "ok", "name": name}


# =============================================================================
# GET /rotation/next_developer
# =============================================================================

@router.get("/next_developer")
async def rotation_next_developer():
    if not ROTATION_ENGINE_AVAILABLE:
        raise HTTPException(503, "Rotational engine unavailable.")

    dev = get_next_developer()
    if not dev:
        raise HTTPException(500, "Rotation engine returned no developer.")

    return {"status": "ok", "developer": dev}


# =============================================================================
# GET /rotation/next_pair
# =============================================================================

@router.get("/next_pair")
async def rotation_next_pair():
    if not ROTATION_ENGINE_AVAILABLE:
        raise HTTPException(503, "Rotational engine unavailable.")

    pair = get_next_pair()
    if not pair.get("ok"):
        raise HTTPException(500, "Rotation engine returned incomplete pair.")

    return {"status": "ok", "pair": pair}


# =============================================================================
# POST /rotation/generate_pair
# =============================================================================

@router.post("/generate_pair")
async def rotation_generate_pair(req: RotateGenerateRequest, extended: bool = Query(False)):
    if not CARTESIA_AVAILABLE:
        raise HTTPException(503, "Cartesia engine unavailable.")
    if not ROTATION_ENGINE_AVAILABLE:
        raise HTTPException(503, "Rotational engine unavailable.")

    pair = get_next_pair()
    name = pair.get("name")
    dev = pair.get("developer")

    if not (name and dev):
        raise HTTPException(500, "Rotation engine returned incomplete pair.")

    voice_id = req.voice_id or VOICE_ID

    name_label = _label_name(name)
    dev_label = _label_dev(dev)

    # NAME STEM
    cached_n = get_cached_stem(name_label)
    if cached_n:
        n_path = cached_n
    else:
        n_path = cartesia_generate(name, name_label, voice_id=voice_id)

    # DEV STEM
    cached_d = get_cached_stem(dev_label)
    if cached_d:
        d_path = cached_d
    else:
        d_path = cartesia_generate(dev, dev_label, voice_id=voice_id)

    response = {
        "status": "ok",
        "rotation": True,
        "pair": {"name": name, "developer": dev},
        "stems": {
            "name": {"label": name_label, "path": n_path},
            "developer": {"label": dev_label, "path": d_path},
        },
    }

    # Extended response for UI/CLI
    if extended:
        idx = load_index().get("stems", {})
        response["stems"]["name"]["cache"] = idx.get(name_label)
        response["stems"]["developer"]["cache"] = idx.get(dev_label)
        response["natural_text"] = {
            "name": _clean_text_from_stem(name_label),
            "developer": _clean_text_from_stem(dev_label),
        }

    return response


# =============================================================================
# GET /rotation/check_bucket
# =============================================================================

@router.get("/check_bucket")
async def rotation_check_bucket(label: str):
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


# =============================================================================
# GET /rotation/pairs_stream — UI preview
# =============================================================================

@router.get("/pairs_stream")
async def rotation_pairs_stream(limit: int = 10):
    if not ROTATION_ENGINE_AVAILABLE:
        raise HTTPException(503, "Rotational engine unavailable.")

    seq = []
    for _ in range(limit):
        p = get_next_pair()
        if p.get("ok"):
            seq.append({"name": p["name"], "developer": p["developer"]})
        else:
            break

    return {"status": "ok", "stream": seq}
