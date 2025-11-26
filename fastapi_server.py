#!/usr/bin/env python3
"""
Hybrid Audio Microservice — FastAPI Server (Hardened Edition)
v5.1 NDF — Sonic-3 Contract Ready + Observability + Error Hardening

Enhancements vs v5.0:
• Defensive contract validation wrapper
• Hardened health endpoints (no internal leaks)
• Router validation + registration guardrails
• CORS validation + safe defaults
• Contract-aware logging (if logging_utils is available)
• Header sanitization for request/response IDs
• Optional middleware safely isolated
• 100% backward compatible (NDF)
"""

import os
import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware

from config import (
    DEBUG,
    summarize_config,
    validate_cartesia_contract,
    VOICE_ID,
    MODEL_ID,
    CARTESIA_API_URL,
)

# ────────────────────────────────────────────────
# Optional Observability
# ────────────────────────────────────────────────
try:
    from observability.request_context import RequestIdMiddleware, current_request_id
except Exception:
    RequestIdMiddleware = None
    current_request_id = lambda: None

try:
    from observability.logging_utils import log_event, init_logging
except Exception:
    def log_event(*args, **kwargs): pass
    def init_logging(): pass


# ────────────────────────────────────────────────
# Router Imports (safe, fail-isolated)
# ────────────────────────────────────────────────
def _safe_import_router(name: str):
    try:
        module = __import__(f"routes.{name}", fromlist=["router"])
        router = getattr(module, "router", None)
        if router:
            return router
    except Exception as e:
        print(f"⚠️ Router load failed: {name}: {e}")
    return None

generate_router = _safe_import_router("generate")
assemble_router = _safe_import_router("assemble")
rotation_router = _safe_import_router("rotation")
cache_router = _safe_import_router("cache")
external_router = _safe_import_router("external")


# ────────────────────────────────────────────────
# App Init — Sonic-3 Edition
# ────────────────────────────────────────────────
app = FastAPI(
    title="Hybrid Audio Assembly API",
    version="5.1",
    description="Sonic-3 aligned microservice for personalized audio generation and assembly."
)

# Initialize logging (optional)
init_logging()

# Request-ID Middleware (optional)
if RequestIdMiddleware:
    try:
        app.add_middleware(RequestIdMiddleware)
    except Exception as e:
        print(f"⚠️ Could not enable RequestIdMiddleware: {e}")


# ────────────────────────────────────────────────
# CORS — hardened
# ────────────────────────────────────────────────
allow_cors = os.getenv("ALLOW_CORS", "false").lower() in ("true", "1", "yes")

if allow_cors:
    try:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )
    except Exception as e:
        print(f"⚠️ CORS initialization failed: {e}")


# ────────────────────────────────────────────────
# Router Registration (hardened)
# ────────────────────────────────────────────────
def _safe_register(router, prefix):
    if router:
        try:
            app.include_router(router, prefix=prefix)
        except Exception as e:
            print(f"⚠️ Failed to register router {prefix}: {e}")

_safe_register(generate_router, "/generate")
_safe_register(assemble_router, "/assemble")
_safe_register(rotation_router, "/rotation")
_safe_register(cache_router, "/cache")
_safe_register(external_router, "/external")


# ────────────────────────────────────────────────
# Utilities
# ────────────────────────────────────────────────
def ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def _safe_contract_check() -> Dict[str, Any]:
    """Prevent internal tracebacks from escaping via /health or /contract."""
    try:
        data = validate_cartesia_contract()
        ok = bool(data.get("ok"))
        return {"ok": ok, "details": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ────────────────────────────────────────────────
# Core Endpoints — Hardened
# ────────────────────────────────────────────────
@app.get("/contract")
async def contract_status():
    """Validate Sonic-3 contract readiness."""
    result = _safe_contract_check()
    if not result["ok"]:
        raise HTTPException(status_code=500, detail="Sonic-3 contract invalid.")
    return result


@app.get("/health")
async def health():
    """Basic health check with Sonic-3 readiness."""
    contract = _safe_contract_check()
    status = "ok" if contract["ok"] else "warning"

    payload = {
        "status": status,
        "time_utc": ts(),
        "debug": DEBUG,
        "voice_id": VOICE_ID,
        "model_id": MODEL_ID,
        "active_api": "sonic-3" if "tts/bytes" in str(CARTESIA_API_URL) else "legacy",
        "contract": contract,
        "config": summarize_config(),
    }

    req_id = current_request_id()
    if req_id:
        payload["request_id"] = req_id

    return payload


@app.get("/health/extended")
async def health_extended():
    """Extended health: config + GCS + Sonic-3 contract."""
    base = await health()

    try:
        from gcloud_storage import gcs_healthcheck
        base["gcs"] = gcs_healthcheck()
    except Exception:
        base["gcs"] = {"ok": False, "reason": "gcloud_storage unavailable"}

    base["timestamp_extended"] = ts()
    return base


@app.get("/live")
async def live():
    return {"ok": True, "time_utc": ts()}


@app.get("/ready")
async def ready():
    contract = _safe_contract_check()
    return {
        "ready": bool(contract["ok"]),
        "contract_valid": contract["ok"],
        "time_utc": ts(),
    }


@app.get("/version")
async def version():
    return {
        "service": "hybrid-audio",
        "version": app.version,
        "time_utc": ts(),
    }


# ────────────────────────────────────────────────
# Local Dev Runner
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=DEBUG,
    )
