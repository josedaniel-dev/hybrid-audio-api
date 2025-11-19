"""
Configuration constants for Hybrid Audio API.

v5.0 NDF — Sonic-3 Contract Core
• Centralizes Sonic-3 /tts/bytes contract in one place
• Fixes malformed Cartesia URL (api/cartesia.ai → api.cartesia.ai)
• Aligns defaults with Cartesia Sonic-3 example (48 kHz, pcm_s16le, wav)
• Exposes build_sonic3_payload() for all generators/routes
• Keeps backward compatibility for existing imports (assemble, routes, cache)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict

# ────────────────────────────────────────────────
# 🔧 Load .env from project root
# ────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    print("⚠️ WARNING: .env not found at:", ENV_PATH)

# ────────────────────────────────────────────────
# 📁 Core Directories (local)
# ────────────────────────────────────────────────

STEMS_DIR = BASE_DIR / "stems"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATE_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"

for _d in (STEMS_DIR, OUTPUT_DIR, LOGS_DIR, TEMPLATE_DIR, DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Structured stems (name/developer) — NDF v3.9
STEMS_NAME_DIR = STEMS_DIR / "name"
STEMS_DEVELOPER_DIR = STEMS_DIR / "developer"
STEMS_NAME_DIR.mkdir(exist_ok=True, parents=True)
STEMS_DEVELOPER_DIR.mkdir(exist_ok=True, parents=True)

# ────────────────────────────────────────────────
# 🎚️ Audio Defaults
# ────────────────────────────────────────────────

CROSSFADE_MS = int(os.getenv("CROSSFADE_MS", 30))
LUFS_TARGET = float(os.getenv("LUFS_TARGET", -16))

# Sonic-3 example payload uses 48000 Hz; we align SAMPLE_RATE to that.
SONIC3_SAMPLE_RATE = int(os.getenv("SONIC3_SAMPLE_RATE", os.getenv("SAMPLE_RATE", 48000)))
SAMPLE_RATE = SONIC3_SAMPLE_RATE

BIT_DEPTH = int(os.getenv("BIT_DEPTH", 16))
SAFE_GAIN_DB = float(os.getenv("SAFE_GAIN_DB", -1.0))

IN_MEMORY_ASSEMBLY = os.getenv("IN_MEMORY_ASSEMBLY", "false").lower() == "true"
ENABLE_SEMANTIC_TIMING = os.getenv("ENABLE_SEMANTIC_TIMING", "true").lower() == "true"

DEFAULT_TEMPLATE = os.getenv("DEFAULT_TEMPLATE", "double_anchor_hybrid_v3_6.json")

DISABLE_NORMALIZATION = os.getenv("DISABLE_NORMALIZATION", "true").lower() == "true"
DISABLE_RESAMPLING = os.getenv("DISABLE_RESAMPLING", "true").lower() == "true"

COMMON_NAMES_FILE = DATA_DIR / "common_names.json"
DEVELOPER_NAMES_FILE = DATA_DIR / "developer_names.json"
ROTATIONS_META_FILE = DATA_DIR / "rotations_meta.json"

# ────────────────────────────────────────────────
# 🧠 Cartesia Sonic-3 Configuration
# ────────────────────────────────────────────────

# Base /tts/bytes endpoint (central truth)
CARTESIA_TTS_URL = os.getenv("CARTESIA_TTS_URL", "https://api.cartesia.ai/tts/bytes")

# Backward-compatible alias (many modules import this)
_raw_api_url = os.getenv("CARTESIA_API_URL", CARTESIA_TTS_URL)
if "api/cartesia.ai" in _raw_api_url:
    # Auto-fix the common typo: https://api/cartesia.ai → https://api.cartesia.ai
    _raw_api_url = _raw_api_url.replace("api/cartesia.ai", "api.cartesia.ai")

CARTESIA_API_URL = _raw_api_url
CARTESIA_URL = CARTESIA_API_URL  # legacy alias, kept for older code

# Cartesia API version; default aligned with support snippet
CARTESIA_VERSION = os.getenv("CARTESIA_VERSION", "2025-04-16")

MODEL_ID = os.getenv("MODEL_ID", "sonic-3")
VOICE_ID = os.getenv("VOICE_ID", "")  # e.g. "9e5605e6-e70a-4a78-bf39-7c6b0db9c359"
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")

# Output format contract for Sonic-3 /tts/bytes
SONIC3_CONTAINER = os.getenv("SONIC3_CONTAINER", "wav")
SONIC3_ENCODING = os.getenv("SONIC3_ENCODING", "pcm_s16le")

# ────────────────────────────────────────────────
# 🗂️ Cache / Registry
# ────────────────────────────────────────────────

STEMS_INDEX_FILE = BASE_DIR / "stems_index.json"
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", 30))

# ────────────────────────────────────────────────
# 📊 Logging / Debug
# ────────────────────────────────────────────────

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_FILE = LOGS_DIR / "hybrid_audio.log"

# ────────────────────────────────────────────────
# ☁️ GCS Integration
# ────────────────────────────────────────────────

GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_FOLDER_STEMS = os.getenv("GCS_FOLDER_STEMS", "stems")
GCS_FOLDER_OUTPUTS = os.getenv("GCS_FOLDER_OUTPUTS", "outputs")
PUBLIC_ACCESS = os.getenv("PUBLIC_ACCESS", "true").lower() == "true"

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")


def is_gcs_enabled() -> bool:
    try:
        return (
            bool(GCS_BUCKET)
            and bool(GOOGLE_APPLICATION_CREDENTIALS)
            and Path(GOOGLE_APPLICATION_CREDENTIALS).exists()
        )
    except Exception:
        return False


URL_BASE_GCS = f"https://storage.googleapis.com/{GCS_BUCKET}" if GCS_BUCKET else ""


def build_gcs_blob_path(folder: str, filename: str) -> str:
    """Utility to normalize <folder>/<filename> paths for GCS."""
    folder = folder.strip("/ ")
    filename = filename.lstrip("/ ")
    return f"{folder}/{filename}" if folder else filename


def build_gcs_uri(folder: str, filename: str) -> str | None:
    """Returns a full https://storage.googleapis.com/... URI if bucket is configured."""
    if not URL_BASE_GCS:
        return None
    blob = build_gcs_blob_path(folder, filename)
    return f"{URL_BASE_GCS}/{blob}"


# ────────────────────────────────────────────────
# Rotational engine dirs
# ────────────────────────────────────────────────

ROTATIONAL_ENGINE_ENABLED = (
    os.getenv("ROTATIONAL_ENGINE_ENABLED", "true").lower() == "true"
)

ROTATIONAL_DATA_DIR = DATA_DIR / "rotational"
ROTATIONAL_DATA_DIR.mkdir(exist_ok=True)

ROTATIONAL_NAME_STEMS_DIR = ROTATIONAL_DATA_DIR / "name"
ROTATIONAL_DEVELOPER_STEMS_DIR = ROTATIONAL_DATA_DIR / "developer"

ROTATIONAL_NAME_STEMS_DIR.mkdir(parents=True, exist_ok=True)
ROTATIONAL_DEVELOPER_STEMS_DIR.mkdir(parents=True, exist_ok=True)

# ────────────────────────────────────────────────
# Template path resolver
# ────────────────────────────────────────────────

def get_template_path(template_name: str | None = None) -> Path:
    name = template_name or os.getenv("DEFAULT_TEMPLATE", DEFAULT_TEMPLATE)
    return TEMPLATE_DIR / name

# ────────────────────────────────────────────────
# 🔖 v5.0 Stem Label Helpers (used by routes/rotation, etc.)
# ────────────────────────────────────────────────

def _norm_label(text: str) -> str:
    return text.strip().lower().replace(" ", "_")


def stem_label_name(name: str) -> str:
    """v5.0 canonical name label: stem.name.<slug>"""
    return f"stem.name.{_norm_label(name)}"


def stem_label_developer(developer: str) -> str:
    """v5.0 canonical developer label: stem.developer.<slug>"""
    return f"stem.developer.{_norm_label(developer)}"

# ────────────────────────────────────────────────
# 🧱 Sonic-3 Payload Builder
# ────────────────────────────────────────────────

def build_sonic3_payload(
    transcript: str,
    voice_id: str | None = None,
    *,
    speed: float = 1.0,
    volume: float = 1.0,
    container: str | None = None,
    encoding: str | None = None,
    sample_rate: int | None = None,
    model_id: str | None = None,
) -> Dict[str, Any]:
    """
    Central Sonic-3 /tts/bytes contract, matching Cartesia's reference:

    {
      "transcript": "Hello, world!",
      "voice": { "mode": "id", "id": "<voice_id>" },
      "generation_config": { "speed": 1, "volume": 1 },
      "output_format": {
          "container": "wav",
          "encoding": "pcm_s16le",
          "sample_rate": 48000
      },
      "model_id": "sonic-3"
    }
    """
    v_id = voice_id or VOICE_ID

    return {
        "transcript": transcript,
        "voice": {
            "mode": "id",
            "id": v_id,
        },
        "generation_config": {
            "speed": float(speed),
            "volume": float(volume),
        },
        "output_format": {
            "container": container or SONIC3_CONTAINER,
            "encoding": encoding or SONIC3_ENCODING,
            "sample_rate": int(sample_rate or SONIC3_SAMPLE_RATE),
        },
        "model_id": model_id or MODEL_ID,
    }

# ────────────────────────────────────────────────
# Contract / Config Diagnostics
# ────────────────────────────────────────────────

def validate_cartesia_contract() -> Dict[str, Any]:
    """
    Lightweight validation to be used by CLI/healthcheck:
      • API key present
      • Endpoint looks like /tts/bytes
      • Voice ID non-empty
    """
    errors: list[str] = []

    if not CARTESIA_API_KEY:
        errors.append("CARTESIA_API_KEY is empty.")

    if "tts/bytes" not in CARTESIA_API_URL:
        errors.append(f"CARTESIA_API_URL does not look like a /tts/bytes endpoint: {CARTESIA_API_URL}")

    if not VOICE_ID:
        errors.append("VOICE_ID is empty (no default voice configured).")

    return {
        "ok": not errors,
        "api_url": CARTESIA_API_URL,
        "version": CARTESIA_VERSION,
        "model_id": MODEL_ID,
        "voice_id_configured": bool(VOICE_ID),
        "sample_rate": SAMPLE_RATE,
        "errors": errors,
    }


def summarize_config() -> Dict[str, Any]:
    return {
        "env_path": str(ENV_PATH),
        "stems_dir": str(STEMS_DIR),
        "output_dir": str(OUTPUT_DIR),
        "voice_id": VOICE_ID,
        "model_id": MODEL_ID,
        "cartesia_api_key_loaded": bool(CARTESIA_API_KEY),
        "cartesia_api_url": CARTESIA_API_URL,
        "sample_rate": SAMPLE_RATE,
        "semantic_timing": ENABLE_SEMANTIC_TIMING,
        "debug": DEBUG,
        "gcs_enabled": is_gcs_enabled(),
    }


if __name__ == "__main__":
    print("🔧 Config Loaded:")
    for k, v in summarize_config().items():
        print("•", k, "=", v)

    print("\n🧪 Cartesia Contract Check:")
    print(validate_cartesia_contract())
