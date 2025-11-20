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
    "validate_template_full",
]


def _build_graph(template: Dict[str, Any]) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {seg.get("id"): set() for seg in template.get("segments", [])}
    for edge in template.get("timing_map", []):
        src = edge.get("from")
        dst = edge.get("to")
        if src in graph and dst:
            graph[src].add(dst)
    return graph


def _detect_cycle(graph: Dict[str, Set[str]]) -> bool:
    visited: Set[str] = set()
    stack: Set[str] = set()

    def dfs(node: str) -> bool:
        if node in stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, set()):
            if dfs(neighbor):
                return True
        stack.remove(node)
        return False

    return any(dfs(n) for n in graph)


def validate_template_full(template: Dict[str, Any]) -> None:
    """Perform extended validation without breaking the base validator."""

    validate_template_structure(template)
    validate_segments(template)
    validate_placeholders(template)
    validate_no_ssml(template)
    validate_timing(template)

    graph = _build_graph(template)
    segment_ids = set(graph.keys())

    # Root detection (nodes without inbound edges)
    inbound: Dict[str, int] = {node: 0 for node in segment_ids}
    for src, targets in graph.items():
        for dst in targets:
            if dst in inbound:
                inbound[dst] += 1
    roots = [node for node, deg in inbound.items() if deg == 0]
    if len(roots) > 1:
        raise TimingMapError(f"Multiple roots detected: {', '.join(sorted(roots))}")
    if not roots:
        raise TimingMapError("No root segment detected; graph must start somewhere")

    # Orphans (no edges at all)
    orphans = [node for node, deg in inbound.items() if deg == 0 and not graph.get(node)]
    if orphans and len(segment_ids) > 1:
        raise TimingMapError(f"Orphan segments without transitions: {', '.join(sorted(orphans))}")

    # Cycles
    if _detect_cycle(graph):
        raise TimingMapError("Timing map contains cycles")

    # Duplicate transitions
    seen_edges: Set[tuple[str, str]] = set()
    for edge in template.get("timing_map", []):
        pair = (edge.get("from"), edge.get("to"))
        if pair in seen_edges:
            raise TimingMapError(f"Duplicate transition detected: {pair[0]} -> {pair[1]}")
        seen_edges.add(pair)

    # Placeholder coverage: all declared placeholders should appear
    declared = set(template.get("placeholders", []))
    found: Set[str] = set()
    for seg in template.get("segments", []):
        found.update(_PLACEHOLDER_RE.findall(seg.get("text") or ""))
    missing_declared = declared - found
    if missing_declared:
        raise TemplateContractError(
            f"Declared placeholders never used: {', '.join(sorted(missing_declared))}"
        )

    # break_ms vs crossfade_ms exclusivity
    for seg in template.get("segments", []):
        break_ms = float(seg.get("break_ms", 0) or 0)
        crossfade_ms = float(seg.get("crossfade_ms", 0) or 0)
        if break_ms > 0 and crossfade_ms > 0:
            raise TemplateContractError(
                f"break_ms and crossfade_ms are mutually exclusive for segment {seg.get('id')}"
            )

        # Estimated duration sanity (warn only)
        est = float(seg.get("estimated_duration_ms", 0) or 0)
        if est and est < len((seg.get("text") or "").split()) * 50:
            print(
                f"[WARN] estimated_duration_ms for segment {seg.get('id')} seems low vs text length"
            )
