#!/usr/bin/env python3
"""
logging_utils.py — Observability helpers (JSON logs + request_id)

v5.0 NDF — Sonic-3 Contract-Aware Logging
──────────────────────────────────────────────────────────────────────────────
• Preserves all v3.6 structured JSON logging behavior
• Integrates request_log_context() (IDs + Sonic-3 contract)
• Every log_event() is automatically enriched with:
      - request_id / correlation_id
      - sonic3_contract: {model_id, voice_id, sample_rate, encoding, version}
• Adds log_contract_warning() for v5.0 cache signature mismatches
• Fully additive and reversible
Author: José Soto
"""

from __future__ import annotations
import json, os, sys, time, uuid
from typing import Any, Dict, Optional
from datetime import datetime
from contextvars import ContextVar

# Optional v5.0 observability context
try:
    from observability.request_context import request_log_context
except Exception:
    # Safe fallback when middleware not loaded
    def request_log_context() -> dict:
        return {}

# Contextvar for request_id (legacy compatibility)
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("_request_id", default=None)

LOG_JSON = os.getenv("LOG_JSON", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "WARNING": 30, "ERROR": 40}
_MIN = _LEVELS.get(LOG_LEVEL, 20)


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def set_request_id(value: Optional[str]) -> None:
    _request_id_ctx.set(value)

def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def _should(level: str) -> bool:
    return _LEVELS.get(level, 20) >= _MIN


# ────────────────────────────────────────────────
# Emit — JSON or human-readable
# ────────────────────────────────────────────────
def _emit(record: Dict[str, Any]) -> None:
    if LOG_JSON:
        sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    else:
        ts = record.get("ts")
        lvl = record.get("level")
        rid = record.get("request_id", "—")
        msg = record.get("message", "")
        sys.stdout.write(f"[{ts}] {lvl} ({rid}) {msg}\n")
    sys.stdout.flush()


# ────────────────────────────────────────────────
# v5.0 — Core logging function (contract-aware)
# ────────────────────────────────────────────────
def log_event(
    level: str = "INFO",
    message: str = "",
    *,
    scope: str = "",
    action: str = "",
    status: str = "ok",
    **fields: Any,
) -> None:

    if not _should(level):
        return

    # 1) Legacy request_id fallback
    rid_legacy = _request_id_ctx.get() or str(uuid.uuid4())

    # 2) v5.0 observability context (IDs + Sonic-3 contract)
    ctx = request_log_context()

    # Extract enriched IDs if present
    rid = ctx.get("request_id") or rid_legacy
    corr = ctx.get("correlation_id")
    sonic3 = ctx.get("sonic3_contract")

    payload = {
        "ts": _now_iso(),
        "level": level,
        "request_id": rid,
        "correlation_id": corr,
        "scope": scope or "general",
        "action": action or "log",
        "status": status,
        "message": message,
        # v5.0 additive Sonic-3 metadata
        "sonic3_contract": sonic3,
        **fields,
    }

    _emit(payload)


# ────────────────────────────────────────────────
# Timing Log
# ────────────────────────────────────────────────
def log_timing(scope: str, action: str, t_start: float, **fields: Any) -> None:
    ms = int((time.time() - t_start) * 1000)
    log_event(
        "INFO",
        f"{action} completed",
        scope=scope,
        action=action,
        duration_ms=ms,
        **fields,
    )


# ────────────────────────────────────────────────
# Error Log
# ────────────────────────────────────────────────
def log_error(message: str, *, scope: str, action: str, **fields: Any) -> None:
    log_event(
        "ERROR",
        message,
        scope=scope,
        action=action,
        status="error",
        **fields,
    )


# ────────────────────────────────────────────────
# v5.0 — Contract mismatch / Stem signature warning
# ────────────────────────────────────────────────
def log_contract_warning(stem_name: str, stored_sig: str, expected_sig: str) -> None:
    """
    Logs a structured warning when cache_manager detects an incompatible stem.
    """
    log_event(
        "WARN",
        f"Sonic-3 contract mismatch for stem '{stem_name}'",
        scope="cache",
        action="contract_mismatch",
        stem_name=stem_name,
        stored_signature=stored_sig,
        expected_signature=expected_sig,
    )


# ────────────────────────────────────────────────
# Local Diagnostic
# ────────────────────────────────────────────────
if __name__ == "__main__":
    log_event("INFO", "logging system bootstrap", scope="obs", action="boot")
    t0 = time.time()
    time.sleep(0.005)
    log_timing("obs", "sleep", t0, note="demo")
    log_error("example error", scope="obs", action="demo", detail="only a test")
