"""
Cache Manager — tracks generated stems in stems_index.json.

v3.6 NDF — Rotational Dataset-Aware Cache
• Adds rotational awareness (rotational flag + dataset origin tracking)
• Adds helper register_rotational_stem() for batch dataset caching
• Extends summarize_cache() to report rotational and dataset metrics
• Retains Sonic-3 metadata, TTL logic, and backward compatibility
──────────────────────────────────────────────────────────────
v3.6 NDF-019 → Deterministic Stem Key + Unified Finder
• Adds stem_key() hash generator for reproducible lookups
• Adds find_or_generate_stem() unified resolver (cache-aware)
• Adds summary_extended() for full audit report
──────────────────────────────────────────────────────────────
v3.9.1 NDF-030 → Additive Rotational Output Structure + Name/Dev-Folders
• Adds support for stems stored in:
      stems/name/<NAME>/*.wav
      stems/developer/<DEV>/*.wav
• Adds helpers for:
      get_stem_by_name()
      get_stem_by_developer()
      cache_stem_with_metadata()
• Does NOT remove or alter existing behavior.
──────────────────────────────────────────────────────────────
v5.0 NDF-Sonic3 → Contract-Aware Cache + Signature
• Adds AUDIO_FORMAT / OUTPUT_ENCODING awareness (from .env when available)
• Adds compute_contract_signature() for Sonic-3 contract binding
• Adds contract_signature + cartesia_version + audio_format + encoding fields
• get_cached_stem() respects contract_signature if present (legacy entries unaffected)
• summarize_cache() and summary_extended() report signature/compat stats
• 100% additive and reversible (no breaking behavior for existing indexes)
Author: José Soto
"""

import json
import os
import datetime
import hashlib
from threading import Lock
from pathlib import Path
from typing import Optional, Dict, Any

from config import (
    STEMS_INDEX_FILE,
    CACHE_TTL_DAYS,
    DEBUG,
    MODEL_ID,
    VOICE_ID,
    SAMPLE_RATE,
    COMMON_NAMES_FILE,
    DEVELOPER_NAMES_FILE,
    CARTESIA_VERSION,
)

# ────────────────────────────────────────────────
# 🔧 Sonic-3 / audio contract context (from .env)
# ────────────────────────────────────────────────
# NOTE: AUDIO_FORMAT comes from .env (see README / config).
# OUTPUT_ENCODING is optional; default matches current Cartesia recommendations.
AUDIO_FORMAT = os.getenv("AUDIO_FORMAT", "wav")
OUTPUT_ENCODING = os.getenv("OUTPUT_ENCODING", "pcm_s16le")

# ────────────────────────────────────────────────
# ⛔ Circular Import Mitigation (unchanged)
# ────────────────────────────────────────────────
def get_cartesia_generate():
    """Lazy importer for cartesia_generate to avoid circular imports."""
    from assemble_message import cartesia_generate
    return cartesia_generate

# Thread lock
_index_lock = Lock()

# Initialize index file if missing
if not STEMS_INDEX_FILE.exists():
    STEMS_INDEX_FILE.write_text(json.dumps({"stems": {}}, indent=2, ensure_ascii=False))


# ────────────────────────────────────────────────
# 📦 Load/save helpers
# ────────────────────────────────────────────────
def load_index() -> dict:
    """Load stem registry JSON into memory; auto-repairs malformed file."""
    with _index_lock:
        try:
            with open(STEMS_INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "stems" not in data:
                    data = {"stems": data}
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            if DEBUG:
                print("⚠️ Index file corrupted or missing — recreating.")
            return {"stems": {}}


def save_index(data: dict) -> None:
    """Safely write stem registry JSON to disk."""
    with _index_lock:
        with open(STEMS_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ────────────────────────────────────────────────
# 🔐 v5.0 — Contract Signature Helpers
# ────────────────────────────────────────────────
def compute_contract_signature(
    text: str,
    voice_id: str = VOICE_ID,
    model_id: str = MODEL_ID,
    sample_rate: int = SAMPLE_RATE,
    audio_format: str = AUDIO_FORMAT,
    encoding: str = OUTPUT_ENCODING,
    cartesia_version: str = CARTESIA_VERSION,
) -> str:
    """
    Compute a deterministic hash binding a stem to the current Sonic-3 contract.

    Any change in:
        - text
        - voice_id / model_id
        - sample_rate
        - audio_format / encoding
        - cartesia_version

    will change the signature and allow us to detect incompatibilities.
    """
    payload = {
        "text": text,
        "voice_id": voice_id,
        "model_id": model_id,
        "sample_rate": sample_rate,
        "audio_format": audio_format,
        "encoding": encoding,
        "cartesia_version": cartesia_version,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def is_entry_contract_compatible(entry: Dict[str, Any]) -> bool:
    """
    v5.0 — Check whether a cached stem entry is compatible with the *current* contract.

    Rules:
      • If contract_signature is missing → treated as legacy/unknown, but NOT rejected.
      • If present → recompute with current globals and compare.
    """
    sig = entry.get("contract_signature")
    if not sig:
        # Legacy entries (pre-v5.0) are accepted to keep NDF guarantees.
        return True

    text = entry.get("text", "")
    voice_id = entry.get("voice_id", VOICE_ID)
    model_id = entry.get("model_id", MODEL_ID)

    expected = compute_contract_signature(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        sample_rate=SAMPLE_RATE,
        audio_format=AUDIO_FORMAT,
        encoding=OUTPUT_ENCODING,
        cartesia_version=CARTESIA_VERSION,
    )

    compatible = (sig == expected)

    if DEBUG and not compatible:
        print(
            f"⚠️ Contract mismatch for stem '{entry.get('path', 'unknown')}'. "
            f"Stored signature={sig}, expected={expected}"
        )

    return compatible

# ────────────────────────────────────────────────
# 📁 Stem Category + Path Resolver
# ────────────────────────────────────────────────

def resolve_stem_storage(label: str) -> Path:
    """
    Determine the correct storage path for a stem based on its label.
    Uses naming_contract.infer_stem_category + naming_contract.build_stem_path.
    Fully additive: does not affect existing flat-cache behavior unless adopted
    by callers (e.g., register_stem).
    """
    from naming_contract import infer_stem_category, build_stem_path

    category = infer_stem_category(label)
    stem_path = build_stem_path(category, label)

    # Ensure folder exists
    stem_path.parent.mkdir(parents=True, exist_ok=True)
    return stem_path


def add_category_to_entry(entry: Dict[str, Any], label: str) -> Dict[str, Any]:
    """
    Adds:
        entry["category"] = inferred category
    without altering any existing keys.
    NDF-SAFE: If category already exists, it is preserved.
    """
    from naming_contract import infer_stem_category

    if "category" not in entry:
        entry["category"] = infer_stem_category(label)
    return entry

# ────────────────────────────────────────────────
# 🧱 register_stem (extended for v5.0, NDF-safe)
# ────────────────────────────────────────────────
def register_stem(
    name: str,
    text: str,
    path: str,
    voice_id: str = VOICE_ID,
    model_id: str = MODEL_ID,
    rotational: bool = False,
    dataset_origin: Optional[str] = None,
) -> None:
    """
    Register or update a stem entry with version bump and metadata.
    NDF-safe: preserves unknown keys.

    v5.0 additions (all additive):
        - audio_format
        - encoding
        - cartesia_version
        - contract_signature
    """
    data = load_index()
    now = datetime.datetime.utcnow().isoformat()
    existing = data["stems"].get(name, {})

    # v5.0 — compute fresh contract signature under current contract
    contract_sig = compute_contract_signature(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        sample_rate=SAMPLE_RATE,
        audio_format=AUDIO_FORMAT,
        encoding=OUTPUT_ENCODING,
        cartesia_version=CARTESIA_VERSION,
    )

    entry = {
        **existing,
        "text": text,
        "path": str(path),
        "voice_id": voice_id,
        "model_id": model_id,
        "sample_rate": SAMPLE_RATE,
        "created": now,
        "rotational": rotational,
        "dataset_origin": dataset_origin,
        "version": existing.get("version", 0) + 1,
        # v5.0 contract fields
        "audio_format": AUDIO_FORMAT,
        "encoding": OUTPUT_ENCODING,
        "cartesia_version": CARTESIA_VERSION,
        "contract_signature": contract_sig,
    }

    data["stems"][name] = entry
    save_index(data)

    if DEBUG:
        tag = "🔁 rotational" if rotational else "🗂️ static"
        print(f"{tag} stem registered/updated: {name} (v{entry['version']}) @ {path}")


def register_rotational_stem(
    name: str,
    text: str,
    path: str,
    dataset_origin: str,
    voice_id: str = VOICE_ID,
    model_id: str = MODEL_ID,
) -> None:
    register_stem(
        name=name,
        text=text,
        path=path,
        voice_id=voice_id,
        model_id=model_id,
        rotational=True,
        dataset_origin=dataset_origin,
    )


# ────────────────────────────────────────────────
# 🔍 NDF-030 — Retrieve cached stems by name/dev folder
# ────────────────────────────────────────────────
def get_stem_by_name(name: str) -> Optional[str]:
    """
    NEW — v3.9.1 NDF-030
    Searches in:
        stems/name/<NAME>/*.wav
    Does NOT modify existing cache logic.
    """
    folder = Path("stems/name") / name.title()
    if not folder.exists():
        return None

    wavs = sorted(folder.glob("*.wav"))
    return str(wavs[-1]) if wavs else None


def get_stem_by_developer(developer: str) -> Optional[str]:
    """
    NEW — v3.9.1 NDF-031
    Searches in:
        stems/developer/<DEV>/*.wav
    """
    folder = Path("stems/developer") / developer.title()
    if not folder.exists():
        return None

    wavs = sorted(folder.glob("*.wav"))
    return str(wavs[-1]) if wavs else None


# ────────────────────────────────────────────────
# 📥 cache_stem_with_metadata
# ────────────────────────────────────────────────
def cache_stem_with_metadata(name: str, developer: str, stem_path: str) -> None:
    """
    NEW — v3.9.1 NDF-032
    Registers a stem in a structured path:
        stems/name/<NAME>/<NAME>_<timestamp>.wav
        stems/developer/<DEV>/<DEV>_<timestamp>.wav

    Does NOT overwrite the classic flat-cache format.
    Fully additive.
    """
    ts_tag = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # name folder
    name_folder = Path("stems/name") / name.title()
    name_folder.mkdir(parents=True, exist_ok=True)
    new_name_path = name_folder / f"{name.title()}_{ts_tag}.wav"
    Path(stem_path).replace(new_name_path)

    # developer folder
    developer_folder = Path("stems/developer") / developer.title()
    developer_folder.mkdir(parents=True, exist_ok=True)
    new_dev_path = developer_folder / f"{developer.title()}_{ts_tag}.wav"
    new_dev_path.write_bytes(new_name_path.read_bytes())

    # Register in STEMS_INDEX_FILE but preserve classic key
    register_stem(
        name=f"{name.lower()}_{developer.lower()}_{ts_tag}",
        text=f"{name}/{developer} rotational stem",
        path=str(new_name_path),
        rotational=True,
        dataset_origin="runtime",
    )

    if DEBUG:
        print(f"📦 NDF cache: stored stem in structured folders @ {new_name_path}")
        print(f"📦 developer copy @ {new_dev_path}")


# ────────────────────────────────────────────────
# Existing: get_cached_stem
# (extended with v5.0 contract check, NDF-safe)
# ────────────────────────────────────────────────
def get_cached_stem(name: str, max_age_days: int = CACHE_TTL_DAYS) -> Optional[str]:
    data = load_index()
    entry = data["stems"].get(name)
    if not entry:
        return None

    path = Path(entry["path"])
    if not path.exists():
        if DEBUG:
            print(f"⚠️ Cached stem missing file: {path}")
        return None

    try:
        created = datetime.datetime.fromisoformat(entry["created"])
        age = (datetime.datetime.utcnow() - created).days
    except Exception:
        age = 0

    if age > max_age_days:
        if DEBUG:
            print(f"🕒 Stem expired: {name} ({age} days old)")
        return None

    # v5.0 — reject stems whose contract_signature no longer matches current contract
    if not is_entry_contract_compatible(entry):
        if DEBUG:
            print(f"🧹 Ignoring incompatible stem (contract changed): {name}")
        return None

    return str(path)


# ────────────────────────────────────────────────
# Expiration Cleanup (unchanged)
# ────────────────────────────────────────────────
def cleanup_expired_stems(max_age_days: int = CACHE_TTL_DAYS) -> int:
    data = load_index()
    now = datetime.datetime.utcnow()
    deleted = []

    for name, entry in list(data["stems"].items()):
        try:
            created = datetime.datetime.fromisoformat(entry.get("created", now.isoformat()))
            if (now - created).days > max_age_days:
                path = Path(entry["path"])
                if path.exists():
                    path.unlink()
                deleted.append(name)
                del data["stems"][name]
        except Exception as e:
            if DEBUG:
                print(f"⚠️ Cleanup error on {name}: {e}")

    if deleted:
        save_index(data)
        if DEBUG:
            print(f"🧹 Removed {len(deleted)} expired stems: {deleted}")

    return len(deleted)


# ────────────────────────────────────────────────
# summarize_cache (extended with v5.0 metrics)
# ────────────────────────────────────────────────
def summarize_cache() -> dict:
    data = load_index()
    stems = data.get("stems", {})
    total = len(stems)
    missing = [n for n, e in stems.items() if not Path(e["path"]).exists()]
    expired = 0
    now = datetime.datetime.utcnow()

    rotational_count = sum(1 for e in stems.values() if e.get("rotational"))
    dataset_sources: Dict[str, int] = {}

    with_signature = 0
    incompatible = 0

    for e in stems.values():
        src = e.get("dataset_origin")
        if src:
            dataset_sources[src] = dataset_sources.get(src, 0) + 1

        try:
            created = datetime.datetime.fromisoformat(e["created"])
            if (now - created).days > CACHE_TTL_DAYS:
                expired += 1
        except Exception:
            pass

        if e.get("contract_signature"):
            with_signature += 1
            if not is_entry_contract_compatible(e):
                incompatible += 1

    return {
        "total_stems": total,
        "rotational_stems": rotational_count,
        "dataset_sources": dataset_sources,
        "missing_files": len(missing),
        "expired_entries": expired,
        "ttl_days": CACHE_TTL_DAYS,
        "index_file": str(STEMS_INDEX_FILE),
        "default_voice": VOICE_ID,
        "default_model": MODEL_ID,
        "sample_rate": SAMPLE_RATE,
        "audio_format": AUDIO_FORMAT,
        "encoding": OUTPUT_ENCODING,
        "cartesia_version": CARTESIA_VERSION,
        "contract_signatures": {
            "with_signature": with_signature,
            "legacy_without_signature": total - with_signature,
            "incompatible_with_current_contract": incompatible,
        },
        "datasets": {
            "common_names_file": str(COMMON_NAMES_FILE),
            "developer_names_file": str(DEVELOPER_NAMES_FILE),
        },
    }


# ────────────────────────────────────────────────
# Deterministic Key (unchanged)
# ────────────────────────────────────────────────
def stem_key(text: str, voice_id: str = VOICE_ID, model_id: str = MODEL_ID) -> str:
    payload = f"{text}|{voice_id}|{model_id}|{SAMPLE_RATE}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


# ────────────────────────────────────────────────
# Unified Finder/Generator (unchanged behavior)
# ────────────────────────────────────────────────
def find_or_generate_stem(
    text: str,
    voice_id: str = VOICE_ID,
    model_id: str = MODEL_ID,
    template: Optional[dict] = None,
) -> str:
    key = stem_key(text, voice_id, model_id)
    cached = get_cached_stem(key)
    if cached:
        if DEBUG:
            print(f"✅ Cache hit for key={key}")
        return cached

    if DEBUG:
        print(f"🧠 Cache miss → generating key={key}")

    generator = get_cartesia_generate()
    path = generator(text, key, voice_id=voice_id, template=template)
    register_stem(name=key, text=text, path=path, voice_id=voice_id, model_id=model_id)
    return path


# ────────────────────────────────────────────────
# Extended Summary (extended for v5.0)
# ────────────────────────────────────────────────
def summary_extended() -> dict:
    base = summarize_cache()
    data = load_index()
    sizes = {}

    for name, entry in data["stems"].items():
        path = Path(entry["path"])
        if path.exists():
            sizes[name] = path.stat().st_size

    base.update({
        "avg_file_size": round(sum(sizes.values()) / len(sizes), 2) if sizes else 0,
        "largest_stem": max(sizes, key=sizes.get) if sizes else None,
        "total_disk_bytes": sum(sizes.values()),
        "hash_preview": list(sizes.keys())[:5],
    })
    return base


# ────────────────────────────────────────────────
# Local Test Harness
# ────────────────────────────────────────────────
if __name__ == "__main__":
    print("🗂️ Cache Manager v5.0 — Sonic-3 Contract-Aware + NDF")
    print(json.dumps(summary_extended(), indent=2))
