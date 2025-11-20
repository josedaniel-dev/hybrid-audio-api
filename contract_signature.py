"""Helpers for computing the Sonic-3 contract signature."""

from __future__ import annotations

import hashlib
from typing import Optional

from config import (
    MODEL_ID,
    SONIC3_CONTAINER,
    SONIC3_ENCODING,
    SONIC3_SAMPLE_RATE,
    CARTESIA_VERSION,
)


def _norm(value: Optional[str]) -> str:
    """Normalize contract fields to deterministic lowercase strings."""
    if value is None:
        return ""
    return str(value).strip().lower()


def compute_contract_signature(
    model_id: Optional[str] = None,
    container: Optional[str] = None,
    encoding: Optional[str] = None,
    sample_rate: Optional[int] = None,
    cartesia_version: Optional[str] = None,
) -> str:
    """Compute a deterministic SHA256 signature of the Sonic-3 contract."""

    parts = [
        _norm(model_id or MODEL_ID),
        _norm(container or SONIC3_CONTAINER),
        _norm(encoding or SONIC3_ENCODING),
        _norm(sample_rate or SONIC3_SAMPLE_RATE),
        _norm(cartesia_version or CARTESIA_VERSION),
    ]

    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["compute_contract_signature"]
