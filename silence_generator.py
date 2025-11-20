"""Utility for generating PCM S16LE silence WAV files.

The Sonic-3 contract requires 48 kHz mono WAV output. This module generates
silence without external dependencies or FFmpeg, relying only on the standard
library. Files are written under ``stems/`` so they can be reused by the
assembly pipeline and cached alongside other stems.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Final
import wave

from config import STEMS_DIR, SONIC3_SAMPLE_RATE, BIT_DEPTH
from naming_contract import build_silence_filename

if BIT_DEPTH != 16:
    raise ValueError("Sonic-3 requires BIT_DEPTH = 16")

_SAMPLE_WIDTH: Final[int] = BIT_DEPTH // 8
_CHANNELS: Final[int] = 1


def _silence_path(duration_ms: int) -> Path:
    filename = build_silence_filename(duration_ms)
    return STEMS_DIR / filename


def generate_silence(duration_ms: int) -> str:
    """Generate a silence WAV file and return its path.

    The PCM payload is constructed manually using ``struct.pack`` to respect
    the instruction that no FFmpeg or numpy should be used.
    """

    if duration_ms < 0:
        raise ValueError("duration_ms cannot be negative")

    target = _silence_path(duration_ms)
    target.parent.mkdir(parents=True, exist_ok=True)

    samples = int(duration_ms * (SONIC3_SAMPLE_RATE / 1000))
    frame = struct.pack("<h", 0)  # 16-bit little endian zero sample
    payload = frame * samples

    with wave.open(str(target), "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(SONIC3_SAMPLE_RATE)
        wf.writeframes(payload)

    return str(target)


def ensure_silence_stem_exists(duration_ms: int) -> str:
    """Return the path to a silence stem, generating it if missing."""

    path = _silence_path(duration_ms)
    if not path.exists():
        return generate_silence(duration_ms)
    return str(path)


__all__ = ["generate_silence", "ensure_silence_stem_exists"]
