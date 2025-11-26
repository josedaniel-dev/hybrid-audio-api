# v5.3-NDF — Structured GCS Logging Layer
# This file introduces a standalone, non-destructive logging module for all
# GCS-related events (existence checks, uploads, downloads, audits, repairs).

import json
import os
from datetime import datetime
from typing import Dict, Any

# Log location (NDF-safe: directory created dynamically)
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "gcs_events.jsonl")


def _ensure_log_dir():
    """Ensure the log directory exists. Non-destructive, safe for all modes."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        # Logging must never interrupt application flow.
        pass


def _write_event(payload: Dict[str, Any]):
    """
    Low-level event writer.
    Always appends (never overwrites) and fails silently on IO errors.
    """
    try:
        _ensure_log_dir()
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        # Silence all errors to avoid breaking API flows.
        pass


def log_gcs_event(event_type: str, payload: Dict[str, Any]):
    """
    Write a single structured GCS event.
    
    Required keys inside `payload`:
    - filename (optional)
    - local_exists (bool)
    - gcs_exists (bool)
    - duration_ms (float)
    - mode (LOCAL | SAFE | PROD)
    - any additional metadata depending on operation type
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        **payload,
    }
    _write_event(event)


def log_gcs_batch(report: Dict[str, Any]):
    """
    Write a batch audit report (e.g., for consistency scans or repair jobs).
    
    Example structure:
    {
        "summary": {...},
        "categories": {...},
        "mode": "SAFE",
        "duration_ms": ...
    }
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "batch_report",
        **report,
    }
    _write_event(event)


def log_gcs_error(operation: str, message: str, meta: Dict[str, Any] = None):
    """
    Write a structured error event related to GCS operations.
    Errors must be logged but must not raise exceptions.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "gcs_error",
        "operation": operation,
        "message": message,
        "meta": meta or {},
    }
    _write_event(event)
