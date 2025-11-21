#!/usr/bin/env python3
"""
Hybrid Audio Assembly — Sonic-3 Edition
v5.1 NDF — Sonic-3 Contract + Cache + Rotation Final Alignment

This version:
    • Fully matches Cartesia’s 2025 requirements:
          - transcript (string)
          - voice.mode="id", voice.id=<VOICE_ID>
          - output_format.container="wav"
          - output_format.encoding="pcm_s16le"
"""

import json
import time
import datetime
import requests
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from config import build_sonic3_payload

from config import (
    STEMS_DIR,
    OUTPUT_DIR,
    CARTESIA_API_URL,
    CARTESIA_API_KEY,
    CARTESIA_VERSION,
    MODEL_ID,
    VOICE_ID,
    CROSSFADE_MS,
    DEBUG,
    ENABLE_SEMANTIC_TIMING,
    SAMPLE_RATE,
    get_template_path,
)

from cache_manager import register_stem, get_cached_stem
from bitmerge_semantic import assemble_with_timing_map_bitmerge
from audio_utils import assemble_clean_merge

# Optional GCS
try:
    from gcloud_storage import upload_to_gcs
    from config import is_gcs_enabled, GCS_FOLDER_OUTPUTS
except Exception:
    upload_to_gcs = None
    def is_gcs_enabled() -> bool:
        return False
    GCS_FOLDER_OUTPUTS = "outputs"

# Rotational hooks
try:
    from rotational_engine import pre_tts_hook, post_tts_hook
except Exception:
    def pre_tts_hook(text, stem_name, **_):
        return text, stem_name
    def post_tts_hook(*_, **__):
        return None


# ============================================================
# Timestamp helpers
# ============================================================

def ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def ts_compact() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


# ============================================================
# Template loading
# ============================================================

def load_template(template_name: Optional[str]) -> Dict[str, Any]:
    try:
        tpl_path = get_template_path(template_name)
        if not tpl_path.exists():
            raise RuntimeError(f"Template not found: {tpl_path}")

        with open(tpl_path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"[{ts()}] ⚠️ Failed to load template: {e}")
        return {"segments": [], "timing_map": [], "voice_config": {}}


# ============================================================
# Template segment rendering
# ============================================================

def build_segments_from_template(
    template: Dict[str, Any],
    name: str,
    developer: str,
) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for seg in template.get("segments", []):
        seg_id = seg.get("id", "")
        txt = (
            seg.get("text", "")
               .replace("{name}", name)
               .replace("{developer}", developer)
        )
        out.append((seg_id, txt))
    return out


# ============================================================
# Convert stem labels back into natural human language
# ============================================================

def _clean_text_from_stem(stem: str) -> str:
    cleaned = (
        stem.replace("stem_name_", "")
            .replace("stem_brand_", "")
            .replace("stem.name.", "")
            .replace("stem.developer.", "")
            .replace("_", " ")
            .strip()
            .title()
    )
    return cleaned


# ============================================================
# ⚡ Sonic-3 TTS Generator
# ============================================================

def cartesia_generate(
    text: str,
    stem_name: str,
    voice_id: str = VOICE_ID,
    template: Optional[Dict[str, Any]] = None,
) -> str:

    raw = text.strip()

    if raw.lower() == stem_name.lower():
        raw = _clean_text_from_stem(stem_name)

    processed_text, _ = pre_tts_hook(raw, stem_name, voice_id=voice_id)
    true_text = processed_text

    cached = get_cached_stem(stem_name)
    if cached:
        if DEBUG:
            print(f"[{ts()}] 🔁 Cache hit → {stem_name}")
        return cached

    print(f"[{ts()}] 🎤 Generating new stem → {stem_name}")
    STEMS_DIR.mkdir(exist_ok=True)

    # ============================================================
    # ⭐ NDF-SAFE PATCH (ÚNICO CAMBIO PERMITIDO)
    #   Sustituye el target plano por el target estructurado
    # ============================================================
    try:
        from naming_contract import infer_stem_category, build_stem_path
        category = infer_stem_category(stem_name)
        structured_path = build_stem_path(category, stem_name)
        structured_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        structured_path = None

    # Target original (NO eliminado)
    out_path = Path(STEMS_DIR) / f"{stem_name}.wav"

    # NDF: prefer structured folder if available
    if structured_path:
        out_path = structured_path
    # ============================================================

    vc = (template or {}).get("voice_config", {})
    speed = float(vc.get("speed", 1.0))
    volume = float(vc.get("volume", 1.0))

    payload = {
        "transcript": true_text,
        "voice": {
            "mode": "id",
            "id": voice_id,
        },
        "generation_config": {
            "speed": speed,
            "volume": volume,
        },
        "output_format": {
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": SAMPLE_RATE,
        },
        "model_id": MODEL_ID,
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": CARTESIA_API_KEY,
        "Cartesia-Version": CARTESIA_VERSION,
    }

    try:
        r = requests.post(
            CARTESIA_API_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()

        with open(out_path, "wb") as f:
            f.write(r.content)

        register_stem(
            name=stem_name,
            text=true_text,
            path=str(out_path),
            voice_id=voice_id,
        )

        post_tts_hook(
            stem_name,
            true_text,
            str(out_path),
            voice_id=voice_id,
            template=template,
        )

        return str(out_path)

    except Exception as e:
        print(f"[{ts()}] ❌ Sonic-3 failure for stem={stem_name}: {e}")
        try:
            print(json.dumps(payload, indent=2))
        except Exception:
            pass
        raise



# ============================================================
# Output basename
# ============================================================

def build_output_basename(
    name: str,
    developer: str,
    mode: str = "semantic",
) -> str:
    n = name.strip().replace(" ", "_")
    d = developer.strip().replace(" ", "_")
    return f"{n}_{d}_{ts_compact()}_{mode}"


# ============================================================
# Semantic timing wrapper
# ============================================================

def assemble_with_timing_map_ndf(
    stems: List[str],
    timing_map: Any,
    basename: str,
) -> str:

    out_path = Path(OUTPUT_DIR) / f"{basename}.wav"

    if isinstance(timing_map, dict):
        timing_map = [
            {
                "from": k[0],
                "to": k[1],
                **v,
            }
            for k, v in timing_map.items()
        ]

    return assemble_with_timing_map_bitmerge(
        stems,
        timing_map,
        str(out_path),
    )


# ============================================================
# Full E2E Pipeline
# ============================================================

def assemble_pipeline(
    name: str,
    developer: str,
    clean_merge: bool = True,
    template_name: Optional[str] = None,
) -> str:

    print(f"\n[{ts()}] 🚀 Assembling message for {name}/{developer}")

    template = load_template(template_name)
    segments = build_segments_from_template(template, name, developer)

    # fallback if template empty
    if not segments:
        print(f"[{ts()}] ⚠️ Missing template → using fallback segments")
        segments = [
            ("static_hey", "Hey"),
            (f"name_{name}", name),
            ("static_info", "it's Luis about your"),
            (f"dev_{developer}", developer),
            ("static_end", "Thank you."),
        ]

    stems: List[str] = []

    for seg_id, text in segments:
        cached = get_cached_stem(seg_id)
        if cached:
            stems.append(cached)
            continue

        stems.append(
            cartesia_generate(
                text=text,
                stem_name=seg_id,
                voice_id=VOICE_ID,
                template=template,
            )
        )

    mode = "semantic" if ENABLE_SEMANTIC_TIMING else "clean"
    basename = build_output_basename(name, developer, mode)

    if ENABLE_SEMANTIC_TIMING:
        return assemble_with_timing_map_ndf(
            stems,
            template.get("timing_map", []),
            basename,
        )

    out = Path(OUTPUT_DIR) / f"{basename}.wav"
    return assemble_clean_merge(stems, out, crossfade_ms=CROSSFADE_MS)


# ============================================================
# Pipeline + GCS upload
# ============================================================

def assemble_pipeline_with_upload(
    name: str,
    developer: str,
    template_name: Optional[str] = None,
    upload: bool = True,
    clean_merge: bool = True,
) -> Dict[str, Any]:

    start = time.time()
    out_path = assemble_pipeline(
        name=name,
        developer=developer,
        clean_merge=clean_merge,
        template_name=template_name,
    )

    file_path = Path(out_path)

    if upload and is_gcs_enabled() and upload_to_gcs:
        upload_meta = upload_to_gcs(str(file_path), folder=GCS_FOLDER_OUTPUTS)
    else:
        upload_meta = {
            "ok": False,
            "mode": "local-only",
            "file_path": str(file_path),
        }

    return {
        "status": "ok",
        "output_file": str(file_path),
        "file_url": upload_meta.get("file_url"),
        "upload": upload_meta,
        "duration_sec": round(time.time() - start, 3),
        "timestamp": ts(),
        "name": name,
        "developer": developer,
    }


# ============================================================
# Unified safe wrapper
# ============================================================

def assemble_pipeline_unified(
    name: str,
    developer: str,
    template_name: Optional[str] = None,
    upload: bool = True,
    clean_merge: bool = True,
) -> Dict[str, Any]:

    try:
        return assemble_pipeline_with_upload(
            name=name,
            developer=developer,
            template_name=template_name,
            upload=upload,
            clean_merge=clean_merge,
        )
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "output_file": None,
            "file_url": None,
            "upload": {},
            "timestamp": ts(),
            "name": name,
            "developer": developer,
        }


# ============================================================
# Diagnostic mode
# ============================================================

if __name__ == "__main__":
    print("🔧 assemble_message.py — Sonic-3 Diagnostic")
    print(" • OUTPUT_DIR:", OUTPUT_DIR)
    print(" • STEMS_DIR :", STEMS_DIR)
    print(" • CARTESIA_API_URL:", CARTESIA_API_URL)
    print(" • SAMPLE_RATE:", SAMPLE_RATE)
