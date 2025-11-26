"""Cartesia Sonic-3 client wrapper.

This module centralizes payload construction, validation and request handling
for the Cartesia Sonic-3 /tts/bytes endpoint. It enforces the Sonic-3 contract
(PCM S16LE, 48 kHz, WAV container) and provides a thin abstraction so other
modules no longer call Cartesia directly.
"""

from __future__ import annotations

import io
import json
import re
import time
import wave
from typing import Any, Dict

import requests

from config import (
    CARTESIA_API_KEY,
    CARTESIA_API_URL,
    CARTESIA_VERSION,
    MODEL_ID,
    SONIC3_CONTAINER,
    SONIC3_ENCODING,
    SONIC3_SAMPLE_RATE,
    VOICE_ID,
    build_sonic3_payload,
)
from errors.sonic3_errors import (
    Sonic3Error,
    OutputValidationError,
    InvalidPayloadError as CoreInvalidPayloadError,
    VoiceIncompatibleError as CoreVoiceIncompatibleError,
)


# -------------------------------------------------
# Error hierarchy (clean & unified)
# -------------------------------------------------

class Sonic3ClientError(Sonic3Error):
    """Base error for Cartesia client failures."""


class InvalidPayloadError(CoreInvalidPayloadError):
    """Raised when the payload does not satisfy the Sonic-3 contract."""


class VoiceIncompatibleError(CoreVoiceIncompatibleError):
    """Raised when the requested voice cannot be used with Sonic-3."""


class RateLimitError(Sonic3ClientError):
    """Raised when Cartesia signals rate limiting."""


# -------------------------------------------------
# SSML detection
# -------------------------------------------------

_SSML_PATTERN = re.compile(r"<[^>]+>")


def detect_voice_compatibility(voice_id: str) -> bool:
    """Return True when the provided voice_id is non-empty and well-formed."""
    if not isinstance(voice_id, str) or not voice_id.strip():
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{6,}(-[A-Za-z0-9_-]{4,})*", voice_id.strip()))


def _assert_no_ssml(text: str) -> None:
    if _SSML_PATTERN.search(text or ""):
        raise InvalidPayloadError("SSML is not allowed in Sonic-3 transcripts.")


# -------------------------------------------------
# Payload construction + validation
# -------------------------------------------------

def build_payload(transcript: str, voice_id: str, speed: float, volume: float) -> Dict[str, Any]:
    _assert_no_ssml(transcript)

    if not detect_voice_compatibility(voice_id):
        raise VoiceIncompatibleError(f"Voice '{voice_id}' is not compatible with Sonic-3")

    if speed <= 0:
        raise InvalidPayloadError("Speed must be greater than zero.")
    if volume <= 0:
        raise InvalidPayloadError("Volume must be greater than zero.")

    payload = build_sonic3_payload(
        transcript=transcript,
        voice_id=voice_id or VOICE_ID,
        speed=speed,
        volume=volume,
        container=SONIC3_CONTAINER,
        encoding=SONIC3_ENCODING,
        sample_rate=SONIC3_SAMPLE_RATE,
        model_id=MODEL_ID,
    )
    validate_payload(payload)
    return payload


def validate_payload(payload: Dict[str, Any]) -> None:
    transcript = payload.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise InvalidPayloadError("transcript must be a non-empty string")
    _assert_no_ssml(transcript)

    voice = payload.get("voice", {})
    if voice.get("mode") != "id":
        raise InvalidPayloadError("voice.mode must be 'id'")

    voice_id = voice.get("id") or VOICE_ID
    if not detect_voice_compatibility(voice_id):
        raise VoiceIncompatibleError(f"Invalid voice id: {voice_id}")

    output_format = payload.get("output_format", {})
    if output_format.get("container") != SONIC3_CONTAINER:
        raise InvalidPayloadError(f"container must be '{SONIC3_CONTAINER}'")
    if output_format.get("encoding") != SONIC3_ENCODING:
        raise InvalidPayloadError(f"encoding must be '{SONIC3_ENCODING}'")
    if int(output_format.get("sample_rate", 0)) != int(SONIC3_SAMPLE_RATE):
        raise InvalidPayloadError(f"sample_rate must be {SONIC3_SAMPLE_RATE}")

    model_id = payload.get("model_id")
    if model_id != MODEL_ID:
        raise InvalidPayloadError(f"model_id must be '{MODEL_ID}'")


# -------------------------------------------------
# Error parsing
# -------------------------------------------------

def parse_sonic3_errors(response_json: Dict[str, Any]) -> None:
    if not response_json:
        return

    message = response_json.get("message") or response_json.get("error")
    error_code = str(response_json.get("code") or "").lower()

    if error_code == "rate_limit" or (message and "rate limit" in message.lower()):
        raise RateLimitError(message or "Rate limit exceeded")

    if message:
        raise Sonic3ClientError(message)


# -------------------------------------------------
# Request dispatch
# -------------------------------------------------

def send_request(payload: Dict[str, Any]) -> bytes:
    validate_payload(payload)

    headers = {
        "Authorization": f"Bearer {CARTESIA_API_KEY}",
        "Content-Type": "application/json",
        "X-Cartesia-Version": CARTESIA_VERSION,
    }

    try:
        response = requests.post(CARTESIA_API_URL, headers=headers, data=json.dumps(payload))
    except Exception as exc:
        raise Sonic3ClientError(f"Failed to contact Cartesia: {exc}") from exc

    if response.status_code == 429:
        raise RateLimitError("Cartesia returned HTTP 429 (rate limited)")

    if response.status_code >= 400:
        try:
            parse_sonic3_errors(response.json())
        except ValueError:
            pass
        raise Sonic3ClientError(f"Cartesia error {response.status_code}: {response.text}")

    content_type = response.headers.get("Content-Type", "")
    if "wav" not in content_type and "octet-stream" not in content_type:
        raise Sonic3ClientError(
            f"Unexpected content type: {content_type or 'unknown'}; expected audio/wav"
        )

    return response.content


# -------------------------------------------------
# Logging + version extraction
# -------------------------------------------------

def log_sonic3_request(payload: Dict[str, Any], response_time_ms: float) -> None:
    transcript_preview = (payload.get("transcript") or "").strip().split()
    preview = " ".join(transcript_preview[:6])
    print(
        f"[Sonic3] {len(payload.get('transcript', ''))} chars | voice={payload.get('voice', {}).get('id')} | "
        f"{response_time_ms:.1f} ms | {preview}"
    )


def extract_cartesia_version(response_headers: Dict[str, Any]) -> str | None:
    for key in ("x-cartesia-version", "X-Cartesia-Version"):
        if key in response_headers:
            return str(response_headers[key])
    return None


# -------------------------------------------------
# Response WAV validation
# -------------------------------------------------

def _validate_wav_bytes(payload: bytes) -> None:
    try:
        with wave.open(io.BytesIO(payload), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
    except wave.Error as exc:
        raise OutputValidationError(f"Invalid WAV bytes returned: {exc}") from exc

    if channels != 1:
        raise OutputValidationError(f"Expected mono output; got {channels} channels")
    if sample_width * 8 != 16:
        raise OutputValidationError(f"Expected 16-bit PCM; got {sample_width * 8} bits")
    if sample_rate != SONIC3_SAMPLE_RATE:
        raise OutputValidationError(f"Expected sample_rate {SONIC3_SAMPLE_RATE}; got {sample_rate}")


# -------------------------------------------------
# Safe full cycle (build → request → validate → return)
# -------------------------------------------------

def safe_generate_wav(transcript: str, voice_id: str, speed: float = 1.0, volume: float = 1.0) -> bytes:
    payload = build_payload(transcript, voice_id, speed, volume)
    start = time.perf_counter()
    wav_bytes = send_request(payload)
    elapsed_ms = (time.perf_counter() - start) * 1000
    log_sonic3_request(payload, elapsed_ms)
    _validate_wav_bytes(wav_bytes)
    return wav_bytes


__all__ = [
    "Sonic3ClientError",
    "InvalidPayloadError",
    "VoiceIncompatibleError",
    "RateLimitError",
    "build_payload",
    "validate_payload",
    "send_request",
    "parse_sonic3_errors",
    "detect_voice_compatibility",
    "log_sonic3_request",
    "extract_cartesia_version",
    "safe_generate_wav",
]
