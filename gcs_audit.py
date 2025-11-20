"""
gcs_audit.py — Hybrid Audio Cloud Audit & Logging (HARDENED)
──────────────────────────────────────────────────────────────
v5.0 NDF — Sonic-3 Contract-Aware Audit Upgrade
• Preserves all existing v3.6 + v3.9.1 behavior
• Adds Sonic-3 contract metadata to audit entries
• Adds contract_signature passthrough for stems
• Adds contract_version grouping for diagnostics
• Additive and reversible (no destructive changes)

v5.0-H1 — Hardening Layer
• Robust JSONL reading (per-line safety, no hard crashes)
• Safer prefix handling for bucket listings
• Optional debug-only console output
• Never raises on audit/log failures (best-effort only)
Author: José Daniel Soto
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List

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
    DEBUG,
)
from gcloud_storage import upload_to_gcs, init_gcs_client

# ────────────────────────────────────────────────
# 📁 Log directories
# ────────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

AUDIT_FILE = LOGS_DIR / "gcs_uploads.jsonl"

STEM_AUDIT_FILE = LOGS_DIR / "gcs_stems.jsonl"
OUTPUT_AUDIT_FILE = LOGS_DIR / "gcs_outputs.jsonl"

STEM_AUDIT_FILE.touch(exist_ok=True)
OUTPUT_AUDIT_FILE.touch(exist_ok=True)


# ────────────────────────────────────────────────
# 🔐 Helpers
# ────────────────────────────────────────────────
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_print(msg: str) -> None:
    """Best-effort debug print (silent in non-DEBUG)."""
    if DEBUG:
        print(msg)


def _safe_read_jsonl(path: Path, limit: int) -> List[Dict[str, Any]]:
    """
    Hardening: read JSONL defensively.
    • Skips malformed lines instead of raising.
    • Honors limit from the end of the file.
    """
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        _safe_print(f"⚠️ Failed to read {path.name}: {e}")
        return []

    selected = lines[-limit:] if limit > 0 else lines
    out: List[Dict[str, Any]] = []

    for line in selected:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception as e:
            _safe_print(f"⚠️ Malformed audit line in {path.name}: {e}")

    return out


def _sanitize_prefix(prefix: str) -> str:
    """Prevent obvious path traversal / weird prefixes."""
    p = (prefix or "").replace("\\", "/")
    p = p.replace("..", "").lstrip("/")
    return p


# ────────────────────────────────────────────────
# 🧠 v5.0 — Contract Metadata Injector
# ────────────────────────────────────────────────
def _inject_contract_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures every audit entry contains Sonic-3 contract info.
    Never overwrites existing keys (NDF rule).
    """
    enriched = dict(entry)

    enriched.setdefault(
        "contract",
        {
            "model_id": MODEL_ID,
            "voice_id": VOICE_ID,
            "sample_rate": SAMPLE_RATE,
            "encoding": SONIC3_ENCODING,
            "container": SONIC3_CONTAINER,
            "cartesia_version": CARTESIA_VERSION,
        },
    )

    if "contract_signature" in entry:
        enriched.setdefault("contract_signature", entry["contract_signature"])

    return enriched


# ────────────────────────────────────────────────
# BASE AUDIT WRITER
# ────────────────────────────────────────────────
def record_audit_entry(entry: Dict[str, Any]) -> None:
    enriched = _inject_contract_metadata(entry)
    enriched["timestamp"] = _now_iso()

    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(enriched, ensure_ascii=False) + "\n")
    except Exception as e:
        _safe_print(f"⚠️ Failed to write audit entry: {e}")


# ────────────────────────────────────────────────
# Structured audit writer
# ────────────────────────────────────────────────
def record_structured_audit(entry: Dict[str, Any], file: Path) -> None:
    enriched = _inject_contract_metadata(entry)
    enriched["timestamp"] = _now_iso()

    try:
        with file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(enriched, ensure_ascii=False) + "\n")
    except Exception as e:
        _safe_print(f"⚠️ Failed to write structured audit to {file.name}: {e}")


# ────────────────────────────────────────────────
# Unified audit logger
# ────────────────────────────────────────────────
def log_gcs_audit(entry: Dict[str, Any]) -> bool:
    try:
        if entry.get("ok"):
            record_audit_entry(entry)
            return True
        return False
    except Exception as e:
        _safe_print(f"⚠️ log_gcs_audit failed: {e}")
        return False


# ────────────────────────────────────────────────
# Stem-specific audit
# ────────────────────────────────────────────────
def log_stem_audit(entry: Dict[str, Any]) -> bool:
    try:
        if entry.get("ok"):
            record_structured_audit(entry, STEM_AUDIT_FILE)
            return True
        return False
    except Exception as e:
        _safe_print(f"⚠️ log_stem_audit failed: {e}")
        return False


# ────────────────────────────────────────────────
# Output-specific audit
# ────────────────────────────────────────────────
def log_output_audit(entry: Dict[str, Any]) -> bool:
    try:
        if entry.get("ok"):
            record_structured_audit(entry, OUTPUT_AUDIT_FILE)
            return True
        return False
    except Exception as e:
        _safe_print(f"⚠️ log_output_audit failed: {e}")
        return False


# ────────────────────────────────────────────────
# Upload with automatic audit
# ────────────────────────────────────────────────
def upload_with_audit(local_file: str, folder: str = "outputs") -> Dict[str, Any]:
    result = upload_to_gcs(local_file, folder)

    if result.get("ok"):
        record_audit_entry(result)
        _safe_print(f"🧾 Audit logged → {AUDIT_FILE.name}")
    else:
        _safe_print(f"⚠️ Upload failed, skipping audit: {result.get('error')}")

    return result


# ────────────────────────────────────────────────
# List functions (hardened)
# ────────────────────────────────────────────────
def list_audit_entries(limit: int = 20) -> List[Dict[str, Any]]:
    return _safe_read_jsonl(AUDIT_FILE, limit)


def list_stem_audits(limit: int = 20) -> List[Dict[str, Any]]:
    return _safe_read_jsonl(STEM_AUDIT_FILE, limit)


def list_output_audits(limit: int = 20) -> List[Dict[str, Any]]:
    return _safe_read_jsonl(OUTPUT_AUDIT_FILE, limit)


# ────────────────────────────────────────────────
# Bucket listing (slightly hardened)
# ────────────────────────────────────────────────
def list_bucket_contents(prefix: str = "") -> List[str]:
    if not is_gcs_enabled():
        _safe_print("⚠️ GCS disabled or credentials missing.")
        return []

    client = init_gcs_client()
    if not client:
        _safe_print("⚠️ Could not initialize GCS client.")
        return []

    try:
        bucket = client.bucket(GCS_BUCKET)
        safe_prefix = _sanitize_prefix(prefix)
        blobs = bucket.list_blobs(prefix=safe_prefix)
        return [b.name for b in blobs]
    except Exception as e:
        _safe_print(f"⚠️ Failed to list bucket contents: {e}")
        return []


# ────────────────────────────────────────────────
# Diagnostic console
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("🧩 GCS Audit Diagnostic (v5.0 Sonic-3 Contract Aware + Hardening)")
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

    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for e in list_audit_entries():
            print(json.dumps(e, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "stems":
        for e in list_stem_audits():
            print(json.dumps(e, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "outputs":
        for e in list_output_audits():
            print(json.dumps(e, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 2 and sys.argv[1] == "upload":
        print(upload_with_audit(sys.argv[2]))
    else:
        print("Usage:")
        print("  python gcs_audit.py upload <path>")
        print("  python gcs_audit.py list")
        print("  python gcs_audit.py stems")
        print("  python gcs_audit.py outputs")
