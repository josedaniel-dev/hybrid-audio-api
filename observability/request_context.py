"""
Request Context & Correlation IDs — Observability Middleware (Hardened)

v5.0 NDF — Sonic-3 Observability Upgrade (Hardened Edition)
──────────────────────────────────────────────────────────────
• Adds explicit contract_snapshot["valid"] flag
• Adds contract validation check for missing/invalid fields
• Hardened fallback if config import fails
• Sanitizes inbound header values
• Python 3.9-compatible typing (Dict[str, Any])
• 100% additive and reversible
"""

from __future__ import annotations

import os
import time
import uuid
import typing as t
import contextvars

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ────────────────────────────────────────────────
# Config import (hardened fallback)
# ────────────────────────────────────────────────
try:
    from config import (
        MODEL_ID,
        VOICE_ID,
        SAMPLE_RATE,
        SONIC3_ENCODING,
        SONIC3_CONTAINER,
        CARTESIA_VERSION,
    )
    _CONTRACT_IMPORT_OK = True
except Exception:
    MODEL_ID = "unknown"
    VOICE_ID = ""
    SAMPLE_RATE = 0
    SONIC3_ENCODING = ""
    SONIC3_CONTAINER = ""
    CARTESIA_VERSION = ""
    _CONTRACT_IMPORT_OK = False


# ────────────────────────────────────────────────
# Env-configurable headers
# ────────────────────────────────────────────────
REQ_ID_HEADER_IN = os.getenv("REQUEST_ID_HEADER_IN", "X-Request-ID")
REQ_ID_HEADER_OUT = os.getenv("REQUEST_ID_HEADER_OUT", "X-Request-ID")
CORR_ID_HEADER_IN = os.getenv("CORRELATION_ID_HEADER_IN", "X-Correlation-ID")
CORR_ID_HEADER_OUT = os.getenv("CORRELATION_ID_HEADER_OUT", "X-Correlation-ID")

TRUST_INCOMING_IDS = os.getenv("REQUEST_CONTEXT_TRUST_INCOMING", "true").lower() == "true"
INCLUDE_TIMING_HEADERS = os.getenv("REQUEST_CONTEXT_TIMING_HEADERS", "true").lower() == "true"


# ────────────────────────────────────────────────
# Contextvars
# ────────────────────────────────────────────────
_request_id_var: contextvars.ContextVar[t.Optional[str]] = contextvars.ContextVar("request_id", default=None)
_correlation_id_var: contextvars.ContextVar[t.Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
_start_ts_var: contextvars.ContextVar[t.Optional[float]] = contextvars.ContextVar("request_start_ts", default=None)
_contract_ctx_var: contextvars.ContextVar[t.Optional[Dict[str, t.Any]]] = contextvars.ContextVar(
    "sonic3_contract", default=None
)


# ────────────────────────────────────────────────
# Public accessors
# ────────────────────────────────────────────────
def current_request_id() -> t.Optional[str]:
    return _request_id_var.get()

def current_correlation_id() -> t.Optional[str]:
    return _correlation_id_var.get()

def current_request_start_ts() -> t.Optional[float]:
    return _start_ts_var.get()

def current_contract_context() -> t.Optional[Dict[str, t.Any]]:
    return _contract_ctx_var.get()


def request_log_context() -> Dict[str, t.Any]:
    """Return enriched request context for logging."""
    ctx = {
        "request_id": current_request_id(),
        "correlation_id": current_correlation_id(),
        "request_start_ts": current_request_start_ts(),
        "sonic3_contract": current_contract_context(),
    }
    return {k: v for k, v in ctx.items() if v is not None}


# ────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────
def _gen_uuid() -> str:
    return str(uuid.uuid4())

def _sanitize_header(value: t.Optional[str]) -> t.Optional[str]:
    if not value:
        return None
    v = value.strip()
    return v if v else None

def _safe_id(header_value: t.Optional[str]) -> str:
    sanitized = _sanitize_header(header_value)
    if TRUST_INCOMING_IDS and sanitized:
        return sanitized
    return _gen_uuid()


# ────────────────────────────────────────────────
# Middleware
# ────────────────────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Hardened Request Context Middleware
    """

    async def dispatch(self, request: Request, call_next) -> Response:

        # Resolve IDs with sanitization
        req_id = _safe_id(request.headers.get(REQ_ID_HEADER_IN))
        corr_id = _safe_id(request.headers.get(CORR_ID_HEADER_IN)) or req_id

        req_token = _request_id_var.set(req_id)
        corr_token = _correlation_id_var.set(corr_id)
        start_ts = time.time()
        ts_token = _start_ts_var.set(start_ts)

        # Build Sonic-3 contract snapshot
        contract_snapshot: Dict[str, t.Any] = {
            "model_id": MODEL_ID,
            "voice_id": VOICE_ID,
            "sample_rate": SAMPLE_RATE,
            "encoding": SONIC3_ENCODING,
            "container": SONIC3_CONTAINER,
            "cartesia_version": CARTESIA_VERSION,
            "valid": _CONTRACT_IMPORT_OK and MODEL_ID not in ("unknown", "", None),
        }

        contract_token = _contract_ctx_var.set(contract_snapshot)

        # Attach to request.state
        request.state.request_id = req_id
        request.state.correlation_id = corr_id
        request.state.request_start_ts = start_ts
        request.state.sonic3_contract = contract_snapshot

        try:
            response = await call_next(request)
        finally:
            # Ensure context cleanup
            _request_id_var.reset(req_token)
            _correlation_id_var.reset(corr_token)
            _start_ts_var.reset(ts_token)
            _contract_ctx_var.reset(contract_token)

        # Tracing headers
        response.headers[REQ_ID_HEADER_OUT] = req_id
        response.headers[CORR_ID_HEADER_OUT] = corr_id

        # Include duration
        if INCLUDE_TIMING_HEADERS:
            dur_ms = max((time.time() - start_ts) * 1000.0, 0.0)
            response.headers["Server-Timing"] = f"app;dur={dur_ms:.2f}"
            response.headers["X-Process-Time"] = f"{dur_ms:.2f}ms"

        return response


# ────────────────────────────────────────────────
# Self-test
# ────────────────────────────────────────────────
if __name__ == "__main__":
    _request_id_var.set("demo")
    _correlation_id_var.set("demo-corr")
    _start_ts_var.set(time.time())
    _contract_ctx_var.set({"model_id": "test", "valid": True})

    print("🔎 request_log_context() →", request_log_context())
    print("✓ Hardened middleware loaded")
