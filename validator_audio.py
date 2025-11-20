"""Strict WAV validator for Sonic-3 outputs."""

from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path
from typing import Dict, Any, Iterable, Tuple, List

from errors.sonic3_errors import OutputValidationError, MergeIntegrityError
from config import SONIC3_SAMPLE_RATE


# -------------------------------------------------------------------------
# WAV HEADER VALIDATION
# -------------------------------------------------------------------------

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

    if bit_depth != 16:
        print(f"[WARN] Non-Sonic-3 bit depth detected ({bit_depth} bits)")

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
        raise OutputValidationError(
            f"Encoding must be pcm_s16le (bit depth 16), got {header['bit_depth']}"
        )


def validate_duration(path: str) -> float:
    header = validate_wav_header(path)
    duration = header["duration_seconds"]
    if duration <= 0:
        raise OutputValidationError("Duration must be positive")
    return duration


# -------------------------------------------------------------------------
# SAMPLE ITERATOR (Unified, safe, bit-depth aware)
# -------------------------------------------------------------------------

def _iter_samples(path: Path, chunk_size: int = 4096) -> Iterable[int]:
    """Yield PCM samples for arbitrary bit depths (8/16/24/32)."""

    with wave.open(str(path), "rb") as wf:
        sample_width = wf.getsampwidth()
        fmt_map = {1: "b", 2: "h", 4: "i"}

        while True:
            frames = wf.readframes(chunk_size)
            if not frames:
                break

            count = len(frames) // sample_width

            # 8, 16, 32-bit: struct unpack
            if sample_width in fmt_map:
                fmt = fmt_map[sample_width]
                samples = struct.unpack(f"<{count}{fmt}", frames)
                for sample in samples:
                    yield sample

            # 24-bit PCM: manual signed conversion
            elif sample_width == 3:
                for i in range(count):
                    chunk = frames[i * 3 : (i + 1) * 3]
                    val = int.from_bytes(chunk, byteorder="little", signed=False)
                    if val & 0x800000:
                        val -= 0x1000000
                    yield val

            else:
                raise MergeIntegrityError(f"Unsupported PCM sample width: {sample_width}")


# -------------------------------------------------------------------------
# MERGE INTEGRITY CHECKS
# -------------------------------------------------------------------------

def validate_merge_integrity(path: str) -> None:
    """Detect NaN, Inf, clipping and empty payload."""

    file_path = Path(path)
    header = validate_wav_header(str(file_path))

    bit_depth = header["bit_depth"]
    max_val = (2 ** (bit_depth - 1)) - 1
    min_val = -2 ** (bit_depth - 1)

    peak = 0
    clipping = False

    for sample in _iter_samples(file_path):
        if math.isinf(sample) or math.isnan(sample):
            raise MergeIntegrityError("Detected invalid sample (NaN/Inf)")

        if sample == max_val or sample == min_val:
            clipping = True

        peak = max(peak, abs(sample))

    if clipping:
        raise MergeIntegrityError("Detected potential clipping at full scale")

    if header["num_frames"] <= 0:
        raise MergeIntegrityError("Empty WAV payload")


# -------------------------------------------------------------------------
# HASHING / STATISTICS
# -------------------------------------------------------------------------

def compute_sha256(path: str) -> str:
    h = hashlib.sha256()
    file_path = Path(path)

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    return h.hexdigest()


def compute_rms(path: str) -> float:
    file_path = Path(path)
    validate_wav_header(str(file_path))

    sample_count = 0
    accum = 0.0

    for sample in _iter_samples(file_path):
        sample_count += 1
        accum += float(sample) ** 2

    if sample_count == 0:
        return 0.0

    return math.sqrt(accum / sample_count)


def detect_clipped_samples(path: str) -> int:
    file_path = Path(path)
    header = validate_wav_header(str(file_path))

    max_val = (2 ** (header["bit_depth"] - 1)) - 1
    min_val = -2 ** (header["bit_depth"] - 1)

    clipped = 0
    for sample in _iter_samples(file_path):
        if sample == max_val or sample == min_val:
            clipped += 1

    return clipped


def detect_silence_regions(
    path: str,
    threshold: int = 0,
    min_duration_ms: int = 50
) -> List[Tuple[int, int]]:
    """Identify continuous silence regions (best-effort heuristic)."""

    file_path = Path(path)
    header = validate_wav_header(str(file_path))
    sample_rate = header["sample_rate"]

    silence_regions: List[Tuple[int, int]] = []

    current_start = None
    current_len = 0

    for idx, sample in enumerate(_iter_samples(file_path)):
        if abs(sample) <= threshold:
            if current_start is None:
                current_start = idx
            current_len += 1
        else:
            if current_start is not None:
                duration_ms = int((current_len / sample_rate) * 1000)
                if duration_ms >= min_duration_ms:
                    silence_regions.append((current_start, duration_ms))
                current_start = None
                current_len = 0

    # Handle trailing silence
    if current_start is not None:
        duration_ms = int((current_len / sample_rate) * 1000)
        if duration_ms >= min_duration_ms:
            silence_regions.append((current_start, duration_ms))

    return silence_regions


# -------------------------------------------------------------------------
# EXPORTS
# -------------------------------------------------------------------------

__all__ = [
    "validate_wav_header",
    "validate_sample_rate",
    "validate_channels",
    "validate_encoding",
    "validate_duration",
    "validate_merge_integrity",
    "compute_sha256",
    "compute_rms",
    "detect_clipped_samples",
    "detect_silence_regions",
]
