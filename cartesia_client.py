"""Cartesia Sonic-3 client wrapper.

This module centralizes payload construction, validation and request handling
for the Cartesia Sonic-3 /tts/bytes endpoint. It enforces the Sonic-3 contract
(PCM S16LE, 48 kHz, WAV container) and provides a thin abstraction so other
modules no longer call Cartesia directly.
"""

from __future__ import annotations

import json
import re
import time
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


class Sonic3ClientError(Exception):
    """Base error for Cartesia client failures."""


class InvalidPayloadError(Sonic3ClientError):  # type: ignore[override]
    """Raised when the payload does not satisfy the Sonic-3 contract."""


class VoiceIncompatibleError(Sonic3ClientError):
    """Raised when the requested voice cannot be used with Sonic-3."""


class RateLimitError(Sonic3ClientError):
    """Raised when Cartesia signals rate limiting."""


_SSML_PATTERN = re.compile(r"<[^>]+>")


def detect_voice_compatibility(voice_id: str) -> bool:
    """Return True when the provided voice_id is non-empty and well-formed.

    The Sonic-3 contract requires ``voice.mode == "id"``. This helper performs
    a lightweight sanity check that the id looks like a UUID or at minimum a
    non-blank token without whitespace. It deliberately avoids strict UUID
    validation to remain forward-compatible with Cartesia voice identifiers.
    """

    if not isinstance(voice_id, str) or not voice_id.strip():
        return False

    # Basic UUID-ish structure (hex and dashes) without enforcing exact length
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{6,}(-[A-Za-z0-9_-]{4,})*", voice_id.strip()))


def _assert_no_ssml(text: str) -> None:
    if _SSML_PATTERN.search(text or ""):
        raise InvalidPayloadError("SSML is not allowed in Sonic-3 transcripts.")


def build_payload(transcript: str, voice_id: str, speed: float, volume: float) -> Dict[str, Any]:
    """Construct a Sonic-3 compliant payload.

    Args:
        transcript: Plain text transcript (no SSML).
        voice_id: Voice identifier compatible with Sonic-3.
        speed: Playback speed multiplier.
        volume: Output volume multiplier.

    Raises:
        InvalidPayloadError: If SSML or invalid parameters are detected.
        VoiceIncompatibleError: When the voice id does not conform to contract.
    """

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
    """Validate that a payload complies with the Sonic-3 contract."""

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


def parse_sonic3_errors(response_json: Dict[str, Any]) -> None:
    """Inspect a Cartesia error payload and raise specific exceptions."""

    if not response_json:
        return

    message = response_json.get("message") or response_json.get("error")
    error_code = str(response_json.get("code") or "").lower()

    if error_code == "rate_limit" or (message and "rate limit" in message.lower()):
        raise RateLimitError(message or "Rate limit exceeded")

    if message:
        raise Sonic3ClientError(message)


def send_request(payload: Dict[str, Any]) -> bytes:
    """Send the Sonic-3 request and return WAV bytes.

    Raises:
        InvalidPayloadError: when payload is malformed.
        RateLimitError: when Cartesia signals throttling.
        Sonic3ClientError: for other API errors.
    """

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
]
