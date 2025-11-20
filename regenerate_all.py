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
from naming_contract import build_stem_filename, build_segment_filename, build_silence_filename, parse_stem_filename
from validator_audio import (
    validate_wav_header,
    compute_sha256,
    compute_rms,
    detect_clipped_samples,
)
from contract_signature import compute_contract_signature


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
    for wav in STEMS_DIR.glob("stem.*.wav"):
        wav.unlink(missing_ok=True)
    for wav in STEMS_DIR.glob("silence.*ms.wav"):
        wav.unlink(missing_ok=True)


def _generate_list_stems(items: Iterable[str], kind: str) -> Dict[str, str]:
    generated: Dict[str, str] = {}
    for item in items:
        if not item:
            continue
        stem_label = build_stem_filename(kind, item)
        try:
            path = cartesia_generate(item, stem_label, voice_id=VOICE_ID)
            generated[stem_label] = path
        except Exception as exc:
            print(f"[WARN] Failed to generate stem {stem_label}: {exc}")
            continue
    return generated


def generate_segment_stem(segment_id: str, text: str) -> Dict[str, str]:
    """Generate a segment-specific stem following the naming contract."""

    stem_label = build_segment_filename(segment_id)
    path = cartesia_generate(text, stem_label, voice_id=VOICE_ID)
    return {stem_label: path}


def _extract_breaks(template: Dict[str, Any]) -> Set[int]:
    durations: Set[int] = set()
    for seg in template.get("segments", []):
        try:
            dur = int(seg.get("break_ms", 0) or 0)
            if dur > 0:
                durations.add(dur)
        except Exception as exc:
            print(f"[WARN] Failed to parse break_ms in segment {seg!r}: {exc}")
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
            generic_label = build_stem_filename("generic", seg_id)
            generic_path = cartesia_generate(text, generic_label, voice_id=VOICE_ID)
            generated[generic_label] = generic_path
            generated.update(generate_segment_stem(seg_id, text))
        except Exception as exc:
            print(f"[WARN] Failed to generate template stem {seg_id}: {exc}")
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
        except Exception as exc:
            print(f"[WARN] Failed to load template via loader {template_file}: {exc}")
            try:
                template = _read_json(template_file)
            except Exception as fallback_exc:
                print(f"[WARN] Failed to parse template fallback {template_file}: {fallback_exc}")
                continue
        silence_durations.update(_extract_breaks(template))
        template_stems.update(_generate_template_stems(template))

    for duration in silence_durations:
        path = ensure_silence_stem_exists(duration)
        generated[build_silence_filename(duration)] = path

    generated.update(template_stems)

    signature = compute_contract_signature()
    index_payload: Dict[str, Any] = {
        "stems": {},
        "audio_format": SONIC3_CONTAINER,
        "encoding": SONIC3_ENCODING,
        "sample_rate": SONIC3_SAMPLE_RATE,
        "cartesia_version": CARTESIA_VERSION,
        "contract_signature": signature,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    def _stem_type(name: str) -> str:
        parsed = parse_stem_filename(name)
        kind = parsed.get("kind", "unknown")
        if kind == "unknown" and name.startswith("silence."):
            return "silence"
        return kind

    for stem_id, path in generated.items():
        try:
            header = validate_wav_header(path)
        except Exception as exc:
            print(f"[WARN] Skipping invalid stem {stem_id}: {exc}")
            continue
        index_payload["stems"][stem_id] = {
            "path": path,
            "audio_format": SONIC3_CONTAINER,
            "encoding": SONIC3_ENCODING,
            "sample_rate": header.get("sample_rate"),
            "duration_seconds": header.get("duration_seconds"),
            "bit_depth": header.get("bit_depth"),
            "channels": header.get("channels"),
            "sha256": compute_sha256(path),
            "rms": compute_rms(path),
            "clipped_samples": detect_clipped_samples(path),
            "stem_type": _stem_type(stem_id),
            "cartesia_version": CARTESIA_VERSION,
            "contract_signature": index_payload["contract_signature"],
        }

    STEMS_INDEX_FILE.write_text(json.dumps(index_payload, indent=2), encoding="utf-8")


__all__ = ["regenerate_all", "generate_segment_stem"]
