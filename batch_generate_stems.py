#!/usr/bin/env python3
"""
Batch Stem Generator — pre-generates stems from lists or template contracts.

v5.1 NDF — Sonic-3 Contract + Canonical Labels

Changes vs v4.2:
    • Uses canonical labels:
          stem.name.<name_slug>
          stem.developer.<dev_slug>
      instead of stem_name_* / stem_brand_*.
    • Rotational batch generation now populates the same cache keys used
      by routes/generate.py and routes/rotation.py.
    • Still never sends stem_id as text (uses _clean_text_from_stem for legacy).
    • Respects cartesia_generate() Sonic-3 contract and cache_manager v5.0.
    • Rotational entries marked with rotational=True + dataset_origin.
"""

import sys
import json
import time
import datetime
import concurrent.futures
from pathlib import Path
from typing import Iterable, Dict, Any, List, Optional, Tuple

from assemble_message import (
    cartesia_generate,
    load_template,
    build_segments_from_template,
    _clean_text_from_stem,
)

from config import (
    DEBUG,
    MODEL_ID,
    VOICE_ID,
    BASE_DIR,
    OUTPUT_DIR,
    CARTESIA_API_URL,
    stem_label_name,
    stem_label_developer,
)

# -------------------------------------------------
# Cache / rotational metadata
# -------------------------------------------------
try:
    from cache_manager import (
        find_or_generate_stem,
        register_rotational_stem,
        stem_key,
    )
    CACHE_OK = True
except Exception:
    CACHE_OK = False

    def find_or_generate_stem(text, voice_id=VOICE_ID, model_id=MODEL_ID, template=None):
        stem = f"stem_generic_{abs(hash((text, voice_id, model_id))) % (10**10)}"
        return cartesia_generate(text, stem, voice_id=voice_id, template=template)

    def register_rotational_stem(*a, **k):
        return None

    def stem_key(text, voice_id=VOICE_ID, model_id=MODEL_ID):
        return f"stem_generic_{abs(hash((text, voice_id, model_id))) % (10**10)}"


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _slugify(text: str) -> str:
    return (
        text.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )


def _ts_compact() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")


def _make_label(prefix: str, item: str) -> str:
    """
    v5.1 — Canonical label resolver:
        • prefix in {"stem_name", "name"}      → stem.name.<slug>
        • prefix in {"stem_brand","developer"} → stem.developer.<slug>
        • else                                 → <prefix>.<slug>
    """
    if prefix in ("stem_name", "name"):
        return stem_label_name(item)
    if prefix in ("stem_brand", "developer", "dev"):
        return stem_label_developer(item)
    return f"{prefix}.{_slugify(item)}"


# -------------------------------------------------
# CORE GENERATION (v5.1)
# -------------------------------------------------
def generate_from_list(
    items: Iterable[str],
    prefix: str,
    voice_overrides: Dict[str, Any] = None,
    max_workers: int = 4,
    retries: int = 2,
    use_cache_key: bool = False,
    rotational: bool = False,
    dataset_origin: Optional[str] = None,
) -> None:
    """
    Batch generator for arbitrary lists.

    Notes:
      • v5.1 rotational mode ignores use_cache_key and always writes canonical
        labels (stem.name.* / stem.developer.*) so routes/rotation + generate
        can reuse stems from the cache.
    """

    raw_items = [i.strip() for i in items if i and i.strip()]
    total = len(raw_items)

    if not total:
        print("⚠️ Empty dataset for generate_from_list.")
        return

    print(f"🚀 Batch prefix '{prefix}' — {total} stems")
    print(f"API={'sonic-3' if 'tts/bytes' in CARTESIA_API_URL else 'legacy'}")
    print(f"voice={VOICE_ID} | model={MODEL_ID}")

    def worker(item: str):
        # v5.1: canonical label (no more stem_name_* / stem_brand_*)
        stem_name = _make_label(prefix, item)

        # Legacy safety: if item is itself a stem id, reconstruct natural text
        if item.lower().startswith("stem_"):
            safe_text = _clean_text_from_stem(item)
        else:
            safe_text = item.strip()

        attempt = 0
        template = None  # no template for bulk (voice_config handled by cartesia_generate if needed)

        while attempt <= retries:
            try:
                # v5.1: In rotational mode we avoid cache_key indirection and
                # always generate under the canonical label used by routes.
                if use_cache_key and CACHE_OK and not rotational:
                    key = stem_key(item, VOICE_ID, MODEL_ID)
                    path = find_or_generate_stem(
                        safe_text,
                        voice_id=VOICE_ID,
                        model_id=MODEL_ID,
                        template=template,
                    )
                    # For non-rotational cache_key usage we don't override label.
                    return item, path, attempt, stem_name

                # Normal Sonic-3 generation under canonical label
                path = cartesia_generate(
                    safe_text,
                    stem_name,
                    voice_id=VOICE_ID,
                    template=template,
                )

                # v5.1: mark as rotational in cache when requested
                if rotational and CACHE_OK:
                    register_rotational_stem(
                        name=stem_name,
                        text=safe_text,
                        path=path,
                        dataset_origin=dataset_origin or f"rotations/{prefix}",
                        voice_id=VOICE_ID,
                        model_id=MODEL_ID,
                    )

                return item, path, attempt, stem_name

            except Exception as e:
                attempt += 1
                if attempt > retries:
                    print(f"❌ {stem_name} failed → {e}")
                    return item, None, attempt, stem_name

                print(f"⚠️ Retry {attempt}/{retries} — {stem_name}")
                time.sleep(1)

    completed = 0
    t0 = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(worker, item): item for item in raw_items}

        for fut in concurrent.futures.as_completed(futures):
            item = futures[fut]
            _, path, attempt, label = fut.result()
            completed += 1

            if path and DEBUG:
                print(f"  ✔ {label} (try {attempt+1})")

    print(f"🎯 Batch complete: {completed}/{total}")
    print(f"⏳ Time: {round(time.time() - t0, 2)}s\n")


# -------------------------------------------------
# TEMPLATE MODE
# -------------------------------------------------
def generate_from_template(template_path: str, first_name="John", developer="Hilton", max_workers=4):
    tpl = load_template(template_path)
    segments = build_segments_from_template(tpl, first_name, developer)
    texts = [t for _, t in segments]

    print(f"📜 Template: {Path(template_path).name} | segments={len(texts)}")
    generate_from_list(
        texts,
        prefix="tpl",
        voice_overrides=tpl.get("voice_config", {}),
        max_workers=max_workers,
    )


# -------------------------------------------------
# ROTATIONAL MODE (v5.1)
# -------------------------------------------------
def generate_rotational_stems(names_path: Path, devs_path: Path, max_workers=6):
    """
    v5.1 rotational batch generator.

    Ensures:
      • Names stored as stem.name.<slug>
      • Developers stored as stem.developer.<slug>
      • Cache entries are compatible with rotation/generate routes.
    """
    print("\n🔁 Rotational Mode")

    from rotational_engine import verify_dataset_integrity, summarize_rotational_cache

    verify_dataset_integrity(names_path, devs_path)

    names = json.loads(names_path.read_text()).get("items", [])
    devs = json.loads(devs_path.read_text()).get("items", [])

    print(f"Names={len(names)} | Developers={len(devs)}")

    # Names → stem.name.*
    generate_from_list(
        names,
        prefix="stem_name",
        use_cache_key=False,  # v5.1: explicit canonical labels
        rotational=True,
        dataset_origin="rotations/names",
        max_workers=max_workers,
    )

    # Developers → stem.developer.*
    generate_from_list(
        devs,
        prefix="stem_brand",  # legacy prefix, label resolver maps to stem.developer.*
        use_cache_key=False,
        rotational=True,
        dataset_origin="rotations/developers",
        max_workers=max_workers,
    )

    summarize_rotational_cache(names, devs)
    print("✅ Rotational stems complete.\n")
