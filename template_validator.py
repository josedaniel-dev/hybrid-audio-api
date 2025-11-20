"""Template validation utilities for Sonic-3 contract."""

from __future__ import annotations

import re
from typing import Dict, Any, Set

from errors.sonic3_errors import TemplateContractError, TimingMapError


_PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")
_SSML_RE = re.compile(r"<[^>]+>")


def validate_template_structure(template: Dict[str, Any]) -> None:
    required_fields = ["template_name", "segments"]
    for field in required_fields:
        if field not in template:
            raise TemplateContractError(f"Missing required field: {field}")
    if not isinstance(template.get("segments"), list) or not template["segments"]:
        raise TemplateContractError("segments must be a non-empty list")


def validate_segments(template: Dict[str, Any]) -> None:
    seen: Set[str] = set()
    for seg in template.get("segments", []):
        seg_id = seg.get("id")
        text = seg.get("text")
        if not seg_id or not isinstance(seg_id, str):
            raise TemplateContractError("Segment missing id")
        if seg_id in seen:
            raise TemplateContractError(f"Duplicate segment id: {seg_id}")
        seen.add(seg_id)
        if not text or not isinstance(text, str):
            raise TemplateContractError(f"Segment {seg_id} missing text")
        if len(text.strip()) == 0:
            raise TemplateContractError(f"Segment {seg_id} has empty text")

        for field in ("gap_ms", "crossfade_ms", "break_ms", "estimated_duration_ms"):
            value = seg.get(field, 0)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                raise TemplateContractError(f"{field} for {seg_id} must be numeric")
            if numeric < 0:
                raise TemplateContractError(f"{field} for {seg_id} cannot be negative")


def validate_placeholders(template: Dict[str, Any]) -> None:
    declared = set(template.get("placeholders", []))
    found: Set[str] = set()
    for seg in template.get("segments", []):
        text = seg.get("text") or ""
        found.update(_PLACEHOLDER_RE.findall(text))

    if declared and not declared.issuperset(found):
        missing = found - declared
        if missing:
            raise TemplateContractError(f"Placeholders not declared: {', '.join(sorted(missing))}")


def validate_no_ssml(template: Dict[str, Any]) -> None:
    for seg in template.get("segments", []):
        text = seg.get("text") or ""
        if _SSML_RE.search(text):
            raise TemplateContractError(f"SSML detected in segment {seg.get('id')}")


def validate_timing(template: Dict[str, Any]) -> None:
    timing_map = template.get("timing_map") or []
    segment_ids = {seg.get("id") for seg in template.get("segments", [])}

    if not isinstance(timing_map, list):
        raise TimingMapError("timing_map must be a list")

    for edge in timing_map:
        src = edge.get("from")
        dst = edge.get("to")
        if src not in segment_ids or dst not in segment_ids:
            raise TimingMapError(f"Transition references unknown segment: {src} -> {dst}")
        for field in ("gap_ms", "crossfade_ms"):
            value = edge.get(field, 0)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                raise TimingMapError(f"{field} for {src}->{dst} must be numeric")
            if numeric < 0:
                raise TimingMapError(f"{field} for {src}->{dst} cannot be negative")

    for seg in template.get("segments", []):
        if seg.get("break_ms") is not None and float(seg.get("break_ms", 0)) < 0:
            raise TimingMapError(f"break_ms for {seg.get('id')} cannot be negative")


__all__ = [
    "validate_template_structure",
    "validate_segments",
    "validate_placeholders",
    "validate_no_ssml",
    "validate_timing",
]
