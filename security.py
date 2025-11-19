# ════════════════════════════════════════════════
# security.py — Hybrid Audio API
# v5.1 NDF — Internal API Key Validation + Sonic-3 Alignment
# Author: José Daniel Soto
# ════════════════════════════════════════════════
"""
Minimal, NDF-safe security layer.

• Validates INTERNAL_API_KEY for protected routes
• Respects MODE (DEV/PROD)
• Fail-open when in DEV AND no key set (local development)
• Fail-closed in PROD or when key is defined
• Zero impact on Sonic-3, caching, rotation, or CLI paths
• Safe import for all routes (no side effects)
"""

import os
from fastapi import Header, HTTPException, status

# ────────────────────────────────────────────────
# Load configuration (fully .env-driven)
# ────────────────────────────────────────────────
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
MODE = os.getenv("MODE", "DEV").upper()

FAIL_OPEN = (MODE == "DEV" and not INTERNAL_API_KEY)
FAIL_CLOSED = not FAIL_OPEN

# ────────────────────────────────────────────────
# Internal API-Key Validator
# ────────────────────────────────────────────────
async def verify_internal_key(x_internal_api_key: str = Header(None)) -> None:
    """
    Ensures the presence of X-Internal-API-Key for protected endpoints.

    Behavior:
        • DEV + no INTERNAL_API_KEY → fail-open (no verification)
        • Otherwise → must match INTERNAL_API_KEY
    """
    if FAIL_OPEN:
        return

    if not x_internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Internal-API-Key header",
        )

    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

# ────────────────────────────────────────────────
# Security Status Summary (for /health/security)
# ────────────────────────────────────────────────
def summarize_security() -> dict:
    return {
        "mode": MODE,
        "internal_key_set": bool(INTERNAL_API_KEY),
        "fail_open": FAIL_OPEN,
        "fail_closed": FAIL_CLOSED,
        "header_required": FAIL_CLOSED,
    }

# ════════════════════════════════════════════════
# Usage Example (FastAPI)
# ════════════════════════════════════════════════
# from fastapi import Depends
# from security import verify_internal_key
#
# @router.get("/internal/secure", dependencies=[Depends(verify_internal_key)])
# async def secure_route():
#     return {"ok": True, "message": "Authorized"}
