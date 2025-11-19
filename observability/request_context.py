"""
Request Context & Correlation IDs — Observability Middleware

v5.0 NDF — Sonic-3 Observability Upgrade
──────────────────────────────────────────────────────────────
• Preserves all v3.6 features (request_id, correlation_id, timing)
• Adds Sonic-3 contract snapshot into request context
• Adds contextvars for contract metadata (model_id, voice_id, sample_rate, encoding)
• Enables enriched log_event() usage with pipeline-level contract context
• 100% additive and reversible
Author: José Daniel Soto · 2025
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

# Sonic-3 contract metadata (imported once)
try:
    from config import (
        MODEL_ID,
        VOICE_ID,
        SAMPLE_RATE,
        SONIC3_ENCODING,
        SONIC3_CONTAINER,
        CARTESIA_VERSION,
    )
except Exception:
    # Graceful fallback — legacy behavior
    MODEL_ID = "unknown"
    VOICE_ID = ""
    SAMPLE_RATE = 0
    SONIC3_ENCODING = ""
    SONIC3_CONTAINER = ""
    CARTESIA_VERSION = ""


# ────────────────────────────────────────────────
# 🔧 Env-configurable headers
# ────────────────────────────────────────────────
REQ_ID_HEADER_IN = os.getenv("REQUEST_ID_HEADER_IN", "X-Request-ID")
REQ_ID_HEADER_OUT = os.getenv("REQUEST_ID_HEADER_OUT", "X-Request-ID")
CORR_ID_HEADER_IN = os.getenv("CORRELATION_ID_HEADER_IN", "X-Correlation-ID")
CORR_ID_HEADER_OUT = os.getenv("CORRELATION_ID_HEADER_OUT", "X-Correlation-ID")

TRUST_INCOMING_IDS = os.getenv("REQUEST_CONTEXT_TRUST_INCOMING", "true").lower() == "true"
INCLUDE_TIMING_HEADERS = os.getenv("REQUEST_CONTEXT_TIMING_HEADERS", "true").lower() == "true"


# ────────────────────────────────────────────────
# 🧠 Contextvars (IDs + Sonic-3 contract block)
# ────────────────────────────────────────────────
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)
_start_ts_var: contextvars.ContextVar[float | None] = contextvars.ContextVar("request_start_ts", default=None)

# NEW — v5.0: Sonic-3 contract snapshot
_contract_ctx_var: contextvars.ContextVar[dict[str, t.Any] | None] = contextvars.ContextVar(
    "sonic3_contract", default=None
)


# ────────────────────────────────────────────────
# Public accessors
# ────────────────────────────────────────────────
def current_request_id() -> str | None:
    return _request_id_var.get()

def current_correlation_id() -> str | None:
    return _correlation_id_var.get()

def current_request_start_ts() -> float | None:
    return _start_ts_var.get()

def current_contract_context() -> dict[str, t.Any] | None:
    """Return the Sonic-3 contract block associated with the request."""
    return _contract_ctx_var.get()


# Aggregated log-friendly payload
def request_log_context() -> dict[str, t.Any]:
    """
    v5.0: Enrich logs with Sonic-3 contract metadata for full observability.
    """
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

def _coalesce_id(header_value: str | None) -> str:
    if TRUST_INCOMING_IDS and header_value:
        return header_value.strip()
    return _gen_uuid()


# ────────────────────────────────────────────────
# 🧱 Middleware
# ────────────────────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    v5.0:
      • request_id + correlation_id
      • timing headers
      • Sonic-3 contract contextvars
      • still 100% reversible and NDF-safe
    """

    def __init__(
        self,
        app,
        request_id_header_in: str = REQ_ID_HEADER_IN,
        request_id_header_out: str = REQ_ID_HEADER_OUT,
        correlation_id_header_in: str = CORR_ID_HEADER_IN,
        correlation_id_header_out: str = CORR_ID_HEADER_OUT,
        trust_incoming: bool = TRUST_INCOMING_IDS,
        include_timing_headers: bool = INCLUDE_TIMING_HEADERS,
    ) -> None:
        super().__init__(app)
        self.request_id_header_in = request_id_header_in
        self.request_id_header_out = request_id_header_out
        self.correlation_id_header_in = correlation_id_header_in
        self.correlation_id_header_out = correlation_id_header_out
        self.trust_incoming = trust_incoming
        self.include_timing_headers = include_timing_headers

    async def dispatch(
        self,
        request: Request,
        call_next: t.Callable[[Request], t.Awaitable[Response]],
    ) -> Response:

        # IDs
        incoming_req_id = request.headers.get(self.request_id_header_in)
        incoming_corr_id = request.headers.get(self.correlation_id_header_in)

        req_id = incoming_req_id.strip() if (self.trust_incoming and incoming_req_id) else _gen_uuid()
        corr_id = incoming_corr_id.strip() if (self.trust_incoming and incoming_corr_id) else req_id

        # Set IDs in contextvars
        req_token = _request_id_var.set(req_id)
        corr_token = _correlation_id_var.set(corr_id)

        start_ts = time.time()
        ts_token = _start_ts_var.set(start_ts)

        # v5.0 — set Sonic-3 contract context
        contract_snapshot = {
            "model_id": MODEL_ID,
            "voice_id": VOICE_ID,
            "sample_rate": SAMPLE_RATE,
            "encoding": SONIC3_ENCODING,
            "container": SONIC3_CONTAINER,
            "cartesia_version": CARTESIA_VERSION,
        }
        contract_token = _contract_ctx_var.set(contract_snapshot)

        # Expose to request.state
        request.state.request_id = req_id
        request.state.correlation_id = corr_id
        request.state.request_start_ts = start_ts
        request.state.sonic3_contract = contract_snapshot

        try:
            response = await call_next(request)
        finally:
            # Reset all contextvars to avoid leaking across async tasks
            _request_id_var.reset(req_token)
            _correlation_id_var.reset(corr_token)
            _start_ts_var.reset(ts_token)
            _contract_ctx_var.reset(contract_token)

        # Add tracing headers
        response.headers[self.request_id_header_out] = req_id
        response.headers[self.correlation_id_header_out] = corr_id

        # Include process timing headers
        if self.include_timing_headers:
            dur_ms = max((time.time() - start_ts) * 1000.0, 0.0)
            response.headers["Server-Timing"] = f"app;dur={dur_ms:.2f}"
            response.headers["X-Process-Time"] = f"{dur_ms:.2f}ms"

        return response


# ────────────────────────────────────────────────
# Self-test
# ────────────────────────────────────────────────
if __name__ == "__main__":
    rid = _gen_uuid()
    cid = _gen_uuid()
    _request_id_var.set(rid)
    _correlation_id_var.set(cid)
    _start_ts_var.set(time.time())
    _contract_ctx_var.set({
        "model_id": MODEL_ID,
        "voice_id": VOICE_ID,
        "sample_rate": SAMPLE_RATE,
        "encoding": SONIC3_ENCODING,
        "container": SONIC3_CONTAINER,
        "cartesia_version": CARTESIA_VERSION,
    })

    print("🔎 request_log_context() →")
    print(request_log_context())

    _request_id_var.set(None)
    _correlation_id_var.set(None)
    _start_ts_var.set(None)
    _contract_ctx_var.set(None)
    print("✅ context cleared")
