"""
Hybrid Audio Microservice — FastAPI Server
v5.0 NDF — Sonic-3 Contract Ready + Unified Router Orchestration

This version:
• Registers all modular routers (generate, assemble, rotation, cache, external)
• Adds Sonic-3 contract validation (/contract)
• Adds unified /health, /health/extended, /ready, /live, /version endpoints
• Adds startup checks (Cartesia contract, config integrity)
• Safe with or without observability middleware
• CORS controlled fully by .env
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
    current_request_id = None

try:
    from observability.logging_utils import log_event, init_logging
except Exception:
    def log_event(*args, **kwargs): pass
    def init_logging(): pass


# ────────────────────────────────────────────────
# Router Imports (NDF-safe)
# ────────────────────────────────────────────────
try:
    from routes.generate import router as generate_router
except Exception:
    generate_router = None

try:
    from routes.assemble import router as assemble_router
except Exception:
    assemble_router = None

try:
    from routes.rotation import router as rotation_router
except Exception:
    rotation_router = None

try:
    from routes.cache import router as cache_router
except Exception:
    cache_router = None

try:
    from routes.external import router as external_router
except Exception:
    external_router = None


# ────────────────────────────────────────────────
# App Init — Sonic-3 Edition
# ────────────────────────────────────────────────
app = FastAPI(
    title="Hybrid Audio Assembly API",
    version="5.0",
    description="Sonic-3 aligned microservice for personalized audio generation and assembly."
)

init_logging()

# Request-ID Middleware (optional)
if RequestIdMiddleware:
    try:
        app.add_middleware(RequestIdMiddleware)
    except Exception as e:
        print(f"⚠️ Could not enable RequestIdMiddleware: {e}")

# CORS via .env
if os.getenv("ALLOW_CORS", "false").lower() in ("true", "1", "yes"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )


# ────────────────────────────────────────────────
# Router Registration
# ────────────────────────────────────────────────
if generate_router:
    app.include_router(generate_router, prefix="/generate")

if assemble_router:
    app.include_router(assemble_router, prefix="/assemble")

if rotation_router:
    app.include_router(rotation_router, prefix="/rotation")

if cache_router:
    app.include_router(cache_router, prefix="/cache")

if external_router:
    app.include_router(external_router, prefix="/external")


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


# ────────────────────────────────────────────────
# Health / Version / Contract
# ────────────────────────────────────────────────
@app.get("/contract")
async def contract_status():
    """Validate Sonic-3 contract readiness."""
    try:
        return validate_cartesia_contract()
    except Exception as e:
        raise HTTPException(500, f"Contract validation failed: {e}")


@app.get("/health")
async def health():
    """Basic health check with Sonic-3 readiness."""
    try:
        contract = validate_cartesia_contract()
        payload = {
            "status": "ok" if contract["ok"] else "warning",
            "time_utc": ts(),
            "debug": DEBUG,
            "voice_id": VOICE_ID,
            "model_id": MODEL_ID,
            "active_api": "sonic-3" if "tts/bytes" in str(CARTESIA_API_URL) else "legacy",
            "contract": contract,
            "config": summarize_config(),
        }
        if callable(current_request_id):
            rid = current_request_id()
            if rid:
                payload["request_id"] = rid
        return payload
    except Exception as e:
        raise HTTPException(500, f"Health failed: {e}")


@app.get("/health/extended")
async def health_extended():
    """Extended health: config + GCS + Sonic-3 contract."""
    try:
        base = await health()
        try:
            from gcloud_storage import gcs_healthcheck
            base["gcs"] = gcs_healthcheck()
        except Exception:
            base["gcs"] = {"ok": False, "reason": "gcloud_storage unavailable"}
        base["timestamp_extended"] = ts()
        return base
    except Exception as e:
        raise HTTPException(500, f"Extended health failed: {e}")


@app.get("/live")
async def live():
    return {"ok": True, "time_utc": ts()}


@app.get("/ready")
async def ready():
    try:
        cfg = summarize_config()
        contract = validate_cartesia_contract()
        return {
            "ready": True if contract["ok"] else False,
            "contract_valid": contract["ok"],
            "time_utc": ts(),
        }
    except Exception as e:
        return {"ready": False, "error": str(e), "time_utc": ts()}


@app.get("/version")
async def version():
    return {"service": "hybrid-audio", "version": app.version, "time_utc": ts()}


# ────────────────────────────────────────────────
# Local Dev
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=DEBUG,
    )
