"""Timing map normalization utilities.

These functions validate and sanitize timing maps produced by the template
system. They ensure consistent non-negative timings, unique segment ids,
and replace declarative ``break_ms`` fields with real silence stems stored
under ``stems/``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Any, Iterable, Set, List

from errors.sonic3_errors import TemplateContractError, TimingMapError
from naming_contract import build_silence_filename
from silence_generator import ensure_silence_stem_exists


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _ensure_non_negative(value: Any, field: str) -> None:
    if value is None:
        return
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise TimingMapError(f"{field} must be numeric; got {value!r}")
    if numeric < 0:
        raise TimingMapError(f"{field} cannot be negative (got {numeric})")


def _segment_ids(segments: Iterable[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for seg in segments:
        seg_id = seg.get("id")
        if not isinstance(seg_id, str) or not seg_id.strip():
            raise TemplateContractError("Each segment requires a non-empty id")
        if seg_id in ids:
            raise TemplateContractError(f"Duplicate segment id detected: {seg_id}")
        ids.add(seg_id)
    return ids


# -------------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------------

def validate_timing_map(timing_map: Dict[str, Any]) -> None:
    """Validate timing map structure and numeric ranges."""

    segments = timing_map.get("segments")
    transitions = timing_map.get("timing_map") or timing_map.get("transitions")

    if not isinstance(segments, list) or not segments:
        raise TemplateContractError("timing_map must include a non-empty 'segments' list")

    known_ids = _segment_ids(segments)

    # Validate segment-level numeric fields
    for seg in segments:
        _ensure_non_negative(seg.get("gap_ms", 0), f"gap_ms for {seg['id']}")
        _ensure_non_negative(seg.get("crossfade_ms", 0), f"crossfade_ms for {seg['id']}")
        _ensure_non_negative(seg.get("break_ms", 0), f"break_ms for {seg['id']}")
        _ensure_non_negative(
            seg.get("estimated_duration_ms", 0),
            f"estimated_duration_ms for {seg['id']}",
        )

    # Validate transitions if present
    if transitions:
        if not isinstance(transitions, list):
            raise TimingMapError("timing_map transitions must be a list")
        for edge in transitions:
            src = edge.get("from")
            dst = edge.get("to")
            if src not in known_ids or dst not in known_ids:
                raise TimingMapError(f"Transition references unknown segment: {src} -> {dst}")

            _ensure_non_negative(edge.get("gap_ms", 0), f"gap_ms for {src}->{dst}")
            _ensure_non_negative(edge.get("crossfade_ms", 0), f"crossfade_ms for {src}->{dst}")


# -------------------------------------------------------------------------
# Normalization of break_ms → silence stems
# -------------------------------------------------------------------------

def normalize_breaks(timing_map: Dict[str, Any]) -> Dict[str, Any]:
    """Return a new timing map with break_ms converted to silence stem references."""

    validate_timing_map(timing_map)
    clone = deepcopy(timing_map)

    for seg in clone.get("segments", []):
        break_ms = int(seg.get("break_ms", 0) or 0)
        if break_ms > 0:
            silence_path = ensure_silence_stem_exists(break_ms)
            seg["break_silence"] = {
                "duration_ms": break_ms,
                "stem_name": build_silence_filename(break_ms),
                "path": silence_path,
            }

    return clone


def resolve_silence_stems(timing_map: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all silence stems referenced by the timing map exist."""

    normalized = normalize_breaks(timing_map)

    for seg in normalized.get("segments", []):
        silence_info = seg.get("break_silence")
        if silence_info:
            duration = int(silence_info.get("duration_ms", 0) or 0)
            silence_info["path"] = ensure_silence_stem_exists(duration)
            silence_info["stem_name"] = build_silence_filename(duration)

    return normalized


# -------------------------------------------------------------------------
# Graph validation (connectivity, cycles, isolation)
# -------------------------------------------------------------------------

def validate_graph_structure(timing_map: Dict[str, Any]) -> None:
    """Validate transitions graph: roots, cycles, connectivity."""

    validate_timing_map(timing_map)

    segments = timing_map.get("segments", [])
    transitions = timing_map.get("timing_map") or timing_map.get("transitions") or []

    graph: Dict[str, Set[str]] = {seg["id"]: set() for seg in segments}
    inbound: Dict[str, int] = {seg["id"]: 0 for seg in segments}

    # Build graph
    for edge in transitions:
        src = edge.get("from")
        dst = edge.get("to")
        if src in graph and dst:
            graph[src].add(dst)
            inbound[dst] += 1

    # Root validation
    roots = [node for node, deg in inbound.items() if deg == 0]
    if len(roots) > 1:
        raise TimingMapError(f"Multiple roots detected: {', '.join(sorted(roots))}")
    if not roots:
        raise TimingMapError("No root node found in timing graph")

    # DFS cycle detection
    visited: Set[str] = set()
    stack: Set[str] = set()

    def dfs(node: str) -> None:
        if node in stack:
            raise TimingMapError("Cycle detected in timing graph")
        if node in visited:
            return

        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, set()):
            dfs(neighbor)
        stack.remove(node)

    for root in roots:
        dfs(root)

    # Isolated nodes
    isolated = [
        node for node, edges in graph.items()
        if not edges and inbound.get(node, 0) == 0
    ]
    if isolated and len(graph) > 1:
        raise TimingMapError(
            f"Isolated timing nodes without transitions: {', '.join(sorted(isolated))}"
        )


# -------------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------------

def auto_fill_missing_transitions(timing_map: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-generate default sequential transitions when none exist."""

    clone = deepcopy(timing_map)
    if clone.get("timing_map"):
        return clone

    segments: List[Dict[str, Any]] = clone.get("segments", [])
    transitions: List[Dict[str, Any]] = []

    for idx in range(len(segments) - 1):
        src = segments[idx].get("id")
        dst = segments[idx + 1].get("id")

        transitions.append({
            "from": src,
            "to": dst,
            "gap_ms": segments[idx].get("gap_ms", 0) or 0,
            "crossfade_ms": segments[idx].get("crossfade_ms", 0) or 0,
        })

    clone["timing_map"] = transitions
    return clone


def enforce_exclusive_break_vs_crossfade(timing_map: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure break_ms disables any crossfade values."""

    clone = deepcopy(timing_map)
    for seg in clone.get("segments", []):
        break_ms = float(seg.get("break_ms", 0) or 0)
        if break_ms > 0:
            seg["crossfade_ms"] = 0
    return clone


# -------------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------------

__all__ = [
    "validate_timing_map",
    "normalize_breaks",
    "resolve_silence_stems",
    "validate_graph_structure",
    "auto_fill_missing_transitions",
    "enforce_exclusive_break_vs_crossfade",
]
