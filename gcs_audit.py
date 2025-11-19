"""
gcs_audit.py — Hybrid Audio Cloud Audit & Logging
──────────────────────────────────────────────────────────────
v5.0 NDF — Sonic-3 Contract-Aware Audit Upgrade
• Preserves all existing v3.6 + v3.9.1 behavior
• Adds Sonic-3 contract metadata to audit entries
• Adds contract_signature passthrough for stems
• Adds contract_version grouping for diagnostics
• Additive and reversible (no destructive changes)
Author: José Daniel Soto
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Imports
from config import (
    GCS_BUCKET,
    GOOGLE_APPLICATION_CREDENTIALS,
    is_gcs_enabled,
    MODEL_ID,
    VOICE_ID,
    SAMPLE_RATE,
    SONIC3_ENCODING,
    SONIC3_CONTAINER,
    CARTESIA_VERSION,
)
from gcloud_storage import upload_to_gcs, init_gcs_client

# ────────────────────────────────────────────────
# 📁 Log directories (existing)
# ────────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

AUDIT_FILE = LOGS_DIR / "gcs_uploads.jsonl"

STEM_AUDIT_FILE = LOGS_DIR / "gcs_stems.jsonl"
OUTPUT_AUDIT_FILE = LOGS_DIR / "gcs_outputs.jsonl"

STEM_AUDIT_FILE.touch(exist_ok=True)
OUTPUT_AUDIT_FILE.touch(exist_ok=True)


# ────────────────────────────────────────────────
# 🧠 v5.0 — Contract Metadata Injector
# ────────────────────────────────────────────────
def _inject_contract_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Additive helper:
        Ensures every audit entry contains Sonic-3 contract info.
        Never overwrites existing keys (NDF rule).
    """
    enriched = dict(entry)

    enriched.setdefault("contract", {
        "model_id": MODEL_ID,
        "voice_id": VOICE_ID,
        "sample_rate": SAMPLE_RATE,
        "encoding": SONIC3_ENCODING,
        "container": SONIC3_CONTAINER,
        "cartesia_version": CARTESIA_VERSION,
    })

    # If stem metadata includes contract_signature (v5.0 cache)
    if "contract_signature" in entry:
        enriched.setdefault("contract_signature", entry["contract_signature"])

    return enriched


# ────────────────────────────────────────────────
# BASE AUDIT WRITER (unchanged, but enriched)
# ────────────────────────────────────────────────
def record_audit_entry(entry: Dict[str, Any]) -> None:
    enriched = _inject_contract_metadata(entry)
    enriched["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, ensure_ascii=False) + "\n")


# ────────────────────────────────────────────────
# v3.9.1 — structured audit helper (extended)
# ────────────────────────────────────────────────
def record_structured_audit(entry: Dict[str, Any], file: Path) -> None:
    enriched = _inject_contract_metadata(entry)
    enriched["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(file, "a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, ensure_ascii=False) + "\n")


# ────────────────────────────────────────────────
# ⭐ Unified audit logger (unchanged behavior)
# ────────────────────────────────────────────────
def log_gcs_audit(entry: Dict[str, Any]) -> bool:
    try:
        if entry.get("ok"):
            record_audit_entry(entry)
            return True
        return False
    except Exception:
        return False


# ────────────────────────────────────────────────
# Stem-specific audit (extended)
# ────────────────────────────────────────────────
def log_stem_audit(entry: Dict[str, Any]) -> bool:
    try:
        if entry.get("ok"):
            record_structured_audit(entry, STEM_AUDIT_FILE)
            return True
        return False
    except Exception:
        return False


# ────────────────────────────────────────────────
# Output-specific audit (extended)
# ────────────────────────────────────────────────
def log_output_audit(entry: Dict[str, Any]) -> bool:
    try:
        if entry.get("ok"):
            record_structured_audit(entry, OUTPUT_AUDIT_FILE)
            return True
        return False
    except Exception:
        return False


# ────────────────────────────────────────────────
# Upload with automatic audit
# ────────────────────────────────────────────────
def upload_with_audit(local_file: str, folder: str = "outputs") -> Dict[str, Any]:
    result = upload_to_gcs(local_file, folder)

    if result.get("ok"):
        # v5.0: Include contract context
        record_audit_entry(result)
        print(f"🧾 Audit logged → {AUDIT_FILE.name}")
    else:
        print(f"⚠️ Upload failed, skipping audit: {result.get('error')}")

    return result


# ────────────────────────────────────────────────
# List functions (unchanged)
# ────────────────────────────────────────────────
def list_audit_entries(limit: int = 20) -> List[Dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    with open(AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(x) for x in lines[-limit:]]


def list_stem_audits(limit: int = 20) -> List[Dict[str, Any]]:
    if not STEM_AUDIT_FILE.exists():
        return []
    with open(STEM_AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(x) for x in lines[-limit:]]


def list_output_audits(limit: int = 20) -> List[Dict[str, Any]]:
    if not OUTPUT_AUDIT_FILE.exists():
        return []
    with open(OUTPUT_AUDIT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(x) for x in lines[-limit:]]


# ────────────────────────────────────────────────
# Bucket listing (unchanged)
# ────────────────────────────────────────────────
def list_bucket_contents(prefix: str = "") -> List[str]:
    if not is_gcs_enabled():
        print("⚠️ GCS disabled or credentials missing.")
        return []
    client = init_gcs_client()
    if not client:
        print("⚠️ Could not initialize GCS client.")
        return []
    try:
        bucket = client.bucket(GCS_BUCKET)
        blobs = bucket.list_blobs(prefix=prefix)
        return [b.name for b in blobs]
    except Exception as e:
        print(f"⚠️ Failed to list bucket contents: {e}")
        return []


# ────────────────────────────────────────────────
# Diagnostic console (banner updated to v5.0)
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("🧩 GCS Audit Diagnostic (v5.0 Sonic-3 Contract Aware)")
    print("─────────────────────────────────────────────")
    print(f"GCS Enabled: {is_gcs_enabled()}")
    print(f"Bucket: {GCS_BUCKET or '—'}")
    print(f"Credentials: {GOOGLE_APPLICATION_CREDENTIALS or '—'}")
    print(f"Model: {MODEL_ID}")
    print(f"Voice: {VOICE_ID}")
    print(f"Sample Rate: {SAMPLE_RATE}")
    print(f"Encoding: {SONIC3_ENCODING}")
    print(f"Cartesia Version: {CARTESIA_VERSION}")
    print("─────────────────────────────────────────────")

    # CLI options preserved
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for e in list_audit_entries(): print(json.dumps(e, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stems":
        for e in list_stem_audits(): print(json.dumps(e, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "outputs":
        for e in list_output_audits(): print(json.dumps(e, indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "upload":
        print(upload_with_audit(sys.argv[2]))
    else:
        print("Usage:")
        print("  python gcs_audit.py upload <path>")
        print("  python gcs_audit.py list")
        print("  python gcs_audit.py stems")
        print("  python gcs_audit.py outputs")
