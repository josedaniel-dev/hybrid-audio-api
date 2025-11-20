"""Naming helpers for Sonic-3 stems and outputs."""

from __future__ import annotations

import datetime
import re
from typing import Final

_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""

    cleaned = text.strip().lower()
    cleaned = _SLUG_PATTERN.sub("_", cleaned)
    cleaned = cleaned.strip("_")
    return cleaned or "unnamed"


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


__all__ = [
    "slugify",
    "build_stem_filename",
    "build_silence_filename",
    "build_output_filename",
]
