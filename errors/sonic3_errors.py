"""Unified Sonic-3 error hierarchy.

This module centralizes the exceptions used by Sonic-3 aligned helpers to
avoid circular imports and to provide consistent error semantics across the
application. Each error is intentionally minimal and does not depend on any
external packages so it can be reused by CLI utilities, FastAPI routes or
standalone scripts without side effects.
"""

from __future__ import annotations


class Sonic3Error(Exception):
    """Base class for all Sonic-3 related errors."""


class InvalidPayloadError(Sonic3Error):
    """Raised when a payload violates the Sonic-3 contract."""


class MissingStemError(Sonic3Error):
    """Raised when a required stem file is not found."""


class VoiceIncompatibleError(Sonic3Error):
    """Raised when a requested voice is incompatible with Sonic-3."""


class TemplateContractError(Sonic3Error):
    """Raised when a template does not satisfy the required schema."""


class TimingMapError(Sonic3Error):
    """Raised when a timing map contains invalid data."""


class BucketObjectNotFound(Sonic3Error):
    """Raised when a GCS object cannot be resolved."""


class OutputValidationError(Sonic3Error):
    """Raised when an output WAV file fails validation."""


class MergeIntegrityError(Sonic3Error):
    """Raised when merged audio data contains invalid samples."""
