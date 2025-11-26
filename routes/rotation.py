"""
routes/rotation.py — v5.2 NDF Sonic-3 Contract
Rotational Name/Developer/Script Stem Generator

Changes in v5.1:
    • Fixes label/schema mismatch (now mirrors assemble_message + cache_manager)
    • Labels are normalized to: stem.name.<name> / stem.developer.<dev>
    • Guarantees Sonic-3–compliant raw-text generation
    • Uses unified cache + index contract
    • Extended mode surfaces all internal metadata cleanly
    • Bucket verifier now uses centralized .env configuration
    • Zero breaking changes to rotational workflow

v5.2 — Script Rotational Support (additive, NDF-safe)
    • Adds stem.script.<segment> label support
    • Adds /rotation/next_script
    • Adds /rotation/generate_script (rotational script stem)
    • Adds /rotation/scripts_stream for UI/CLI previews
    • Extends /rotation/check_bucket to handle script stems via
      structured GCS folders when available
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any

# -----------------------------------------------
# 🔥 ADITIVO — FIX para monkeypatch
# -----------------------------------------------
import config as _config
# (No se elimina nada existente, solo se añade esta línea)

# Core contracts
try:
    from assemble_message import cartesia_generate, _clean_text_from_stem
    from cache_manager import get_cached_stem, load_index
    from config import VOICE_ID, GCS_FOLDER_STEMS, GCS_FOLDER_STEMS_SCRIPT
    CARTESIA_AVAILABLE = True
except Exception:
    CARTESIA_AVAILABLE = False
    VOICE_ID = ""  # type: ignore
    GCS_FOLDER_STEMS = "stems"  # type: ignore
    GCS_FOLDER_STEMS_SCRIPT = "stems/script"  # type: ignore

# Rotational engine (names/developers)
try:
    from rotational_engine import (
        get_next_name,
        get_next_developer,
        get_next_pair,
    )
    ROTATION_ENGINE_AVAILABLE = True
except Exception:
    ROTATION_ENGINE_AVAILABLE = False

# Script rotational engine (optional, v5.2)
try:
    from scripts_engine import get_next_script  # rotational script provider
    SCRIPT_ROTATION_AVAILABLE = True
except Exception:
    SCRIPT_ROTATION_AVAILABLE = False

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


def _label_script(s: str) -> str:
    """v5.2 — canonical script label."""
    return f"stem.script.{_norm(s)}"


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

    response: Dict[str, Any] = {
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
# v5.2 — SCRIPT ROTATION
# =============================================================================

@router.get("/next_script")
async def rotation_next_script():
    """
    Returns the next script segment from the rotational script engine.
    """
    if not SCRIPT_ROTATION_AVAILABLE:
        raise HTTPException(503, "Script rotational engine unavailable.")

    script = get_next_script()
    if not script:
        raise HTTPException(500, "Rotation engine returned no script segment.")

    return {"status": "ok", "script": script}


@router.post("/generate_script")
async def rotation_generate_script(req: RotateGenerateRequest, extended: bool = Query(False)):
    """
    Generate (or reuse from cache) a rotational script stem:

        stem.script.<slug>
    """
    if not CARTESIA_AVAILABLE:
        raise HTTPException(503, "Cartesia engine unavailable.")
    if not SCRIPT_ROTATION_AVAILABLE:
        raise HTTPException(503, "Script rotational engine unavailable.")

    script = get_next_script()
    if not script:
        raise HTTPException(500, "Rotation engine returned no script segment.")

    voice_id = req.voice_id or VOICE_ID
    script_label = _label_script(script)

    cached_s = get_cached_stem(script_label)
    if cached_s:
        s_path = cached_s
    else:
        s_path = cartesia_generate(script, script_label, voice_id=voice_id)

    response: Dict[str, Any] = {
        "status": "ok",
        "rotation": True,
        "script": script,
        "stem": {"label": script_label, "path": s_path},
    }

    if extended:
        idx = load_index().get("stems", {})
        response["stem"]["cache"] = idx.get(script_label)
        response["natural_text"] = {
            "script": _clean_text_from_stem(script_label),
        }

    return response


@router.get("/scripts_stream")
async def rotation_scripts_stream(limit: int = 10):
    """
    UI/CLI helper: preview a stream of upcoming script segments.
    """
    if not SCRIPT_ROTATION_AVAILABLE:
        raise HTTPException(503, "Script rotational engine unavailable.")

    stream = []
    for _ in range(limit):
        s = get_next_script()
        if not s:
            break
        stream.append({"script": s, "label": _label_script(s)})

    return {"status": "ok", "stream": stream}


# =============================================================================
# GET /rotation/check_bucket
# =============================================================================

@router.get("/check_bucket")
async def rotation_check_bucket(label: str):
    """
    Check whether a cached stem also exists in GCS.

    v5.2:
        • For stem.script.* → uses GCS_FOLDER_STEMS_SCRIPT
        • Else             → uses GCS_FOLDER_STEMS (legacy)
    """

    # ADITIVO — FIX para permitir monkeypatch de pytest
    if not (_config.is_gcs_enabled() and gcs_check_file_exists):
        raise HTTPException(503, "GCS integration unavailable.")

    filename = f"{label}.wav"

    # Route to proper structured folder when possible
    if label.startswith("stem.script."):
        base_folder = GCS_FOLDER_STEMS_SCRIPT
    else:
        base_folder = GCS_FOLDER_STEMS

    uri = f"{base_folder}/{filename}"

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
