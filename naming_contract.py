"""Naming helpers for Sonic-3 stems and outputs."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Final, Dict

_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


# -------------------------------------------------
# Slug utilities
# -------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    cleaned = text.strip().lower()
    cleaned = _SLUG_PATTERN.sub("_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned or "unnamed"


# -------------------------------------------------
# Filename builders
# -------------------------------------------------

def build_stem_filename(kind: str, label: str) -> str:
    """Construct a deterministic stem filename."""
    kind_slug = slugify(kind)
    label_slug = slugify(label)
    return f"stem.{kind_slug}.{label_slug}.wav"


def build_silence_filename(duration_ms: int) -> str:
    """Return the silence filename for a duration."""
    return f"silence.{int(duration_ms)}ms.wav"


def build_output_filename(name: str, developer: str, merge_mode: str) -> str:
    """Build an output WAV filename following the contract."""
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
    return f"output.{slugify(name)}.{slugify(developer)}.{ts}.{slugify(merge_mode)}.wav"


def build_segment_filename(segment_id: str) -> str:
    """Return the canonical filename for a template segment stem."""
    return f"segment.{slugify(segment_id)}.wav"


# -------------------------------------------------
# Parsing helpers
# -------------------------------------------------

def parse_stem_filename(filename: str) -> Dict[str, str]:
    """Parse a stem-like filename into its components."""

    name = Path(filename).name

    patterns = {
        "stem.name": r"^stem\.name\.([^.]+)\.wav$",
        "stem.developer": r"^stem\.developer\.([^.]+)\.wav$",
        "stem.generic": r"^stem\.generic\.([^.]+)\.wav$",
        "segment": r"^segment\.([^.]+)\.wav$",
        "silence": r"^silence\.([0-9]+)ms\.wav$",
    }

    for kind, pattern in patterns.items():
        match = re.match(pattern, name)
        if match:
            return {"kind": kind.split(".")[-1], "label": match.group(1)}

    return {"kind": "unknown", "label": name}


# -------------------------------------------------
# Validation
# -------------------------------------------------

def validate_stem_kind(kind: str) -> None:
    """Ensure the stem kind is one of the contract-approved categories."""
    allowed = {"name", "developer", "generic", "segment", "silence"}
    if kind not in allowed:
        raise ValueError(f"Invalid stem kind '{kind}'. Allowed: {', '.join(sorted(allowed))}")


# -------------------------------------------------
# Exported symbols
# -------------------------------------------------

__all__ = [
    "slugify",
    "build_stem_filename",
    "build_silence_filename",
    "build_output_filename",
    "build_segment_filename",
    "parse_stem_filename",
    "validate_stem_kind",
]
