"""Full regeneration pipeline for Sonic-3 stems.

This script deletes legacy stems, regenerates contract-aligned assets (names,
developers, generic/template stems and silence stems) and rewrites the
``stems_index.json`` registry with Sonic-3 signature metadata.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, Iterable, Set

from assemble_message import cartesia_generate, load_template
from config import (
    STEMS_DIR,
    STEMS_INDEX_FILE,
    MODEL_ID,
    VOICE_ID,
    SONIC3_CONTAINER,
    SONIC3_ENCODING,
    SONIC3_SAMPLE_RATE,
    CARTESIA_VERSION,
    COMMON_NAMES_FILE,
    DEVELOPER_NAMES_FILE,
    TEMPLATE_DIR,
)
from silence_generator import ensure_silence_stem_exists
from validator_audio import validate_wav_header


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        raw = f.read()
    # Allow // comments for compatibility with existing templates
    sanitized = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("//"))
    return json.loads(sanitized)


def _load_list(path: Path) -> Iterable[str]:
    if not path.exists():
        return []
    data = _read_json(path)
    if isinstance(data, list):
        return data
    return []


def _cleanup_stems() -> None:
    for wav in STEMS_DIR.rglob("*.wav"):
        wav.unlink(missing_ok=True)


def _generate_list_stems(items: Iterable[str], kind: str) -> Dict[str, str]:
    generated: Dict[str, str] = {}
    for item in items:
        if not item:
            continue
        stem_label = f"stem.{kind}.{item}" if not item.startswith("stem.") else item
        try:
            path = cartesia_generate(item, stem_label, voice_id=VOICE_ID)
            generated[stem_label] = path
        except Exception:
            continue
    return generated


def _extract_breaks(template: Dict[str, Any]) -> Set[int]:
    durations: Set[int] = set()
    for seg in template.get("segments", []):
        try:
            dur = int(seg.get("break_ms", 0) or 0)
            if dur > 0:
                durations.add(dur)
        except Exception:
            continue
    return durations


def _generate_template_stems(template: Dict[str, Any]) -> Dict[str, str]:
    generated: Dict[str, str] = {}
    for seg in template.get("segments", []):
        seg_id = seg.get("id")
        text = seg.get("text")
        if not seg_id or not text:
            continue
        try:
            path = cartesia_generate(text, seg_id, voice_id=VOICE_ID)
            generated[seg_id] = path
        except Exception:
            continue
    return generated


def regenerate_all() -> None:
    """Orchestrate regeneration of all stems and silence assets."""

    _cleanup_stems()

    names = _load_list(Path(COMMON_NAMES_FILE))
    developers = _load_list(Path(DEVELOPER_NAMES_FILE))

    generated: Dict[str, str] = {}
    generated.update(_generate_list_stems(names, "name"))
    generated.update(_generate_list_stems(developers, "developer"))

    silence_durations: Set[int] = set()
    template_stems: Dict[str, str] = {}

    for template_file in TEMPLATE_DIR.glob("*.json"):
        try:
            template = load_template(str(template_file))
        except Exception:
            try:
                template = _read_json(template_file)
            except Exception:
                continue
        silence_durations.update(_extract_breaks(template))
        template_stems.update(_generate_template_stems(template))

    for duration in silence_durations:
        path = ensure_silence_stem_exists(duration)
        generated[f"silence.{duration}ms"] = path

    generated.update(template_stems)

    index_payload: Dict[str, Any] = {
        "stems": {},
        "audio_format": SONIC3_CONTAINER,
        "encoding": SONIC3_ENCODING,
        "sample_rate": SONIC3_SAMPLE_RATE,
        "cartesia_version": CARTESIA_VERSION,
        "contract_signature": f"{MODEL_ID}|{SONIC3_CONTAINER}|{SONIC3_ENCODING}|{SONIC3_SAMPLE_RATE}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    for stem_id, path in generated.items():
        try:
            header = validate_wav_header(path)
        except Exception:
            continue
        index_payload["stems"][stem_id] = {
            "path": path,
            "audio_format": SONIC3_CONTAINER,
            "encoding": SONIC3_ENCODING,
            "sample_rate": header.get("sample_rate"),
            "duration_seconds": header.get("duration_seconds"),
            "cartesia_version": CARTESIA_VERSION,
            "contract_signature": index_payload["contract_signature"],
        }

    STEMS_INDEX_FILE.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")


__all__ = ["regenerate_all"]
