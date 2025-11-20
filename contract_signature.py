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


def compute_contract_signature(
    model_id: Optional[str] = None,
    container: Optional[str] = None,
    encoding: Optional[str] = None,
    sample_rate: Optional[int] = None,
    cartesia_version: Optional[str] = None,
) -> str:
    """Compute a deterministic SHA256 signature of the Sonic-3 contract."""

    parts = [
        model_id or MODEL_ID,
        container or SONIC3_CONTAINER,
        encoding or SONIC3_ENCODING,
        str(sample_rate or SONIC3_SAMPLE_RATE),
        cartesia_version or CARTESIA_VERSION,
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["compute_contract_signature"]
