"""Strict WAV validator for Sonic-3 outputs."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Dict, Any

from errors.sonic3_errors import OutputValidationError, MergeIntegrityError
from config import SONIC3_SAMPLE_RATE


def validate_wav_header(path: str) -> Dict[str, Any]:
    """Validate WAV header and return metadata."""

    file_path = Path(path)
    if not file_path.exists():
        raise OutputValidationError(f"File not found: {path}")

    try:
        with wave.open(str(file_path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            comp_type = wf.getcomptype()
            duration = nframes / float(framerate) if framerate else 0.0
    except wave.Error as exc:
        raise OutputValidationError(f"Invalid WAV file: {exc}") from exc

    if comp_type != "NONE":
        raise OutputValidationError(f"Unsupported compression type: {comp_type}")

    bit_depth = sample_width * 8
    if bit_depth not in (16, 24, 32):
        raise OutputValidationError(f"Unexpected bit depth: {bit_depth}")

    if duration <= 0:
        raise OutputValidationError("WAV duration must be greater than zero")

    return {
        "sample_rate": framerate,
        "channels": channels,
        "bit_depth": bit_depth,
        "duration_seconds": duration,
        "num_frames": nframes,
    }


def validate_sample_rate(path: str, expected: int = SONIC3_SAMPLE_RATE) -> None:
    header = validate_wav_header(path)
    if int(header["sample_rate"]) != int(expected):
        raise OutputValidationError(
            f"Sample rate mismatch: expected {expected}, got {header['sample_rate']}"
        )


def validate_channels(path: str, expected: int = 1) -> None:
    header = validate_wav_header(path)
    if int(header["channels"]) != int(expected):
        raise OutputValidationError(
            f"Channel count mismatch: expected {expected}, got {header['channels']}"
        )


def validate_encoding(path: str) -> None:
    header = validate_wav_header(path)
    if int(header["bit_depth"]) != 16:
        raise OutputValidationError(f"Encoding must be pcm_s16le (bit depth 16), got {header['bit_depth']}")


def validate_duration(path: str) -> float:
    header = validate_wav_header(path)
    duration = header["duration_seconds"]
    if duration <= 0:
        raise OutputValidationError("Duration must be positive")
    return duration


def _iter_samples(path: Path, chunk_size: int = 4096):
    with wave.open(str(path), "rb") as wf:
        sample_width = wf.getsampwidth()
        if sample_width != 2:
            raise MergeIntegrityError("Only 16-bit PCM is supported for merge integrity checks")

        while True:
            frames = wf.readframes(chunk_size)
            if not frames:
                break
            count = len(frames) // sample_width
            samples = struct.unpack(f"<{count}h", frames)
            for sample in samples:
                yield sample


def validate_merge_integrity(path: str) -> None:
    """Detect NaN/Inf/clipping in PCM samples."""

    file_path = Path(path)
    header = validate_wav_header(str(file_path))
    validate_encoding(str(file_path))

    peak = 0
    clipping = False
    for sample in _iter_samples(file_path):
        if math.isinf(sample) or math.isnan(sample):
            raise MergeIntegrityError("Detected invalid sample (NaN/Inf)")
        if sample in (32767, -32768):
            clipping = True
        peak = max(peak, abs(sample))

    if clipping:
        raise MergeIntegrityError("Detected potential clipping at full scale")

    if header["num_frames"] <= 0:
        raise MergeIntegrityError("Empty WAV payload")


__all__ = [
    "validate_wav_header",
    "validate_sample_rate",
    "validate_channels",
    "validate_encoding",
    "validate_duration",
    "validate_merge_integrity",
]
