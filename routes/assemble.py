from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict, Any, Optional

# Core Sonic-3 pipeline
from assemble_message import (
    load_template,
    build_segments_from_template,
    cartesia_generate,
)

from bitmerge_semantic import assemble_with_timing_map_bitmerge
from audio_utils import assemble_clean_merge
from cache_manager import get_cached_stem, load_index

from config import (
    OUTPUT_DIR,
    ENABLE_SEMANTIC_TIMING,
    stem_label_name,
    stem_label_developer,
    SONIC3_SAMPLE_RATE,
)

# Optional GCS
try:
    from gcloud_storage import (
        upload_output_file,
        upload_stem_file,
        list_bucket_contents,
        resolve_gcs_blob_name,
    )
    from config import (
        is_gcs_enabled,
        GCS_FOLDER_OUTPUTS,
        GCS_FOLDER_STEMS,
    )
except Exception:
    upload_output_file = None
    upload_stem_file = None
    list_bucket_contents = None
    resolve_gcs_blob_name = None
    is_gcs_enabled = lambda: False
    GCS_FOLDER_OUTPUTS = "outputs"
    GCS_FOLDER_STEMS = "stems"

router = APIRouter()

# ============================================================
# Models
# ============================================================

class TemplateAssembleRequest(BaseModel):
    first_name: str
    developer: str
    template: str
    upload: Optional[bool] = False


class SegmentAssemblyRequest(BaseModel):
    segments: List[str]
    segment_ids: Optional[List[str]] = None
    upload: Optional[bool] = False


# ============================================================
# POST /assemble/template
# ============================================================

@router.post("/template")
async def assemble_template(
    req: TemplateAssembleRequest,
    extended: bool = Query(False)
):
    """
    Template-based assembly (Sonic-3 aligned)
        • cartesia_generate() for each segment
        • semantic merge if ENABLE_SEMANTIC_TIMING=True
        • clean merge fallback
        • GCS upload optional
    """

    try:
        tpl = load_template(req.template)
        segments = tpl.get("segments", [])
        timing_map = tpl.get("timing_map", [])

        if not segments:
            raise HTTPException(400, "Template contains no segments")

        name = req.first_name.strip().title()
        dev = req.developer.strip().title()

        # Render template text → replaces {name}, {developer}
        rendered_segments = build_segments_from_template(tpl, name, dev)

        stems: List[str] = []
        stem_meta: Dict[str, Any] = {}

        for seg_id, text in rendered_segments:
            cached = get_cached_stem(seg_id)
            if cached:
                stems.append(cached)
                stem_meta[seg_id] = {"status": "cached", "path": cached}
            else:
                path = cartesia_generate(text, seg_id, template=tpl)
                stems.append(path)
                stem_meta[seg_id] = {"status": "generated", "path": path}

        # Output filename
        filename = f"{name}_{dev}__template"
        out_path = Path(OUTPUT_DIR) / f"{filename}.wav"

        # Normalize timing map format
        if isinstance(timing_map, dict):
            timing_map = [
                {"from": k[0], "to": k[1], **v}
                for k, v in timing_map.items()
            ]

        # Merge path
        if ENABLE_SEMANTIC_TIMING:
            assemble_with_timing_map_bitmerge(stems, timing_map, str(out_path))
        else:
            assemble_clean_merge(stems, out_path, crossfade_ms=8)

        # GCS upload
        upload_meta = {}
        if req.upload and upload_output_file and is_gcs_enabled():
            upload_meta = upload_output_file(str(out_path))

        # Extended metadata
        if extended:
            index = load_index()
            return {
                "status": "ok",
                "segments": len(stems),
                "output_file": str(out_path),
                "upload": upload_meta,
                "stem_details": stem_meta,
                "timing_map": timing_map,
                "template_voice_config": tpl.get("voice_config", {}),
                "cache_index_preview": list(index.get("stems", {}).keys())[:20],
                "sample_rate": SONIC3_SAMPLE_RATE,
            }

        return {
            "status": "ok",
            "segments": len(stems),
            "output_file": str(out_path),
            "upload": upload_meta,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Template assembly failed: {e}")


# ============================================================
# POST /assemble/segments  (manual freeform assembly)
# ============================================================

@router.post("/segments")
async def assemble_segments(req: SegmentAssemblyRequest):
    """
    Manual text segments → stems → clean merge only.
    """

    if not req.segments:
        raise HTTPException(400, "No segments provided")

    stems = []
    ids = req.segment_ids or []

    for i, text in enumerate(req.segments):
        seg_id = ids[i] if i < len(ids) else f"segment_{i}"

        cached = get_cached_stem(seg_id)
        if cached:
            stems.append(cached)
        else:
            stems.append(cartesia_generate(text, seg_id))

    out_path = Path(OUTPUT_DIR) / "assembled_custom.wav"
    assemble_clean_merge(stems, out_path, crossfade_ms=8)

    upload_meta = {}
    if req.upload and upload_output_file and is_gcs_enabled():
        upload_meta = upload_output_file(str(out_path))

    return {
        "status": "ok",
        "segments": len(stems),
        "output_file": str(out_path),
        "upload": upload_meta,
    }


# ============================================================
# GET /assemble/output_location
# ============================================================

@router.get("/output_location")
async def output_location():
    """
    Returns most recent local output file.
    """

    try:
        out_dir = Path(OUTPUT_DIR)
        if not out_dir.exists():
            return {"status": "empty", "output_dir": str(out_dir)}

        files = sorted(out_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
        if not files:
            return {"status": "empty", "output_dir": str(out_dir)}

        last_file = files[-1]

        return {
            "status": "ok",
            "latest_output": str(last_file),
            "timestamp": last_file.stat().st_mtime,
        }

    except Exception as e:
        raise HTTPException(500, f"Failed to read output directory: {e}")


# ============================================================
# GET /assemble/check/stem_in_bucket
# ============================================================

@router.get("/check/stem_in_bucket")
async def check_stem_in_bucket(stem_name: str):
    """
    Checks if a stem exists in GCS → stems/<stem_name>.wav
    """

    if not (list_bucket_contents and is_gcs_enabled()):
        raise HTTPException(503, "GCS integration unavailable")

    prefix = f"{GCS_FOLDER_STEMS}/{stem_name}"
    contents = list_bucket_contents(prefix=prefix)
    exists = any(prefix in b for b in contents)

    return {
        "status": "ok",
        "stem": stem_name,
        "exists": exists,
    }


# ============================================================
# GET /assemble/check/output_in_bucket
# ============================================================

@router.get("/check/output_in_bucket")
async def check_output_in_bucket(filename: str):
    """
    Checks if a merged output exists in GCS → outputs/<filename>
    """

    if not (list_bucket_contents and is_gcs_enabled()):
        raise HTTPException(503, "GCS integration unavailable")

    prefix = f"{GCS_FOLDER_OUTPUTS}/{filename}"
    contents = list_bucket_contents(prefix=prefix)
    exists = any(prefix in b for b in contents)

    return {
        "status": "ok",
        "file": filename,
        "exists": exists,
    }
