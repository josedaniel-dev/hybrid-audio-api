#!/usr/bin/env python3
"""
scripts_engine.py — Hybrid Audio API (SCRIPT STEM ENGINE)
──────────────────────────────────────────────────────────────
v1.0 NDF — Additive Module
• Introduces SCRIPT stems as first-class citizens
• Fully compatible with:
      - naming_contract (stem.script.*)
      - config (stems/script)
      - gcloud_storage (structured paths)
      - cache_manager (optional)
• Never modifies existing stem types (name/developer/generic)
• Safe, reversible, non-destructive

Author: José Soto
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Core helpers
from config import (
    STEMS_SCRIPT_DIR,
    stem_label_script,
    resolve_structured_stem_path,
)

from assemble_message import cartesia_generate, _clean_text_from_stem

# Optional cache
try:
    from cache_manager import (
        register_rotational_stem,
        find_or_generate_stem,
        stem_key,
    )
    CACHE_OK = True
except Exception:
    CACHE_OK = False


# ───────────────────────────────────────────────
# SCRIPT STEM CREATION
# ───────────────────────────────────────────────
def generate_script_stem(
    text: str,
    *,
    segment_name: Optional[str] = None,
    retries: int = 2,
    rotational: bool = False,
    dataset_origin: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a SCRIPT stem from text.

    Produces a canonical label:
        stem.script.<slug>

    Stores stem in:
        stems/script/<label>.wav

    Respects:
        - Sonic-3 contract
        - cache_manager (optional)
    """

    safe_text = text.strip()
    if safe_text.lower().startswith("stem."):
        safe_text = _clean_text_from_stem(safe_text)

    label_base = segment_name or safe_text
    label = stem_label_script(label_base)

    stem_path = resolve_structured_stem_path(label)

    attempt = 0
    while attempt <= retries:
        try:
            wav_path = cartesia_generate(
                safe_text,
                label,
                voice_id=None,   # caller decides default voice
                template=None,
            )

            if rotational and CACHE_OK:
                register_rotational_stem(
                    name=label,
                    text=safe_text,
                    path=wav_path,
                    dataset_origin=dataset_origin or "scripts/manual",
                )

            return {
                "ok": True,
                "label": label,
                "text": safe_text,
                "path": wav_path,
                "attempts": attempt + 1,
            }

        except Exception as e:
            attempt += 1
            if attempt > retries:
                return {
                    "ok": False,
                    "label": label,
                    "error": str(e),
                    "attempts": attempt,
                }
            time.sleep(1)


# ───────────────────────────────────────────────
# BULK GENERATION
# ───────────────────────────────────────────────
def generate_script_stems_bulk(
    items: List[str],
    *,
    rotational: bool = False,
    dataset_origin: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Bulk generator for SCRIPT stems.

    Each item is treated as:
        - raw text for SCRIPT generation
    """
    results = []
    for item in items:
        if not item or not item.strip():
            continue
        res = generate_script_stem(
            item,
            rotational=rotational,
            dataset_origin=dataset_origin,
        )
        results.append(res)
    return results


# ───────────────────────────────────────────────
# DISCOVERY & INDEXING
# ───────────────────────────────────────────────
def list_script_stems() -> List[str]:
    """
    Lists all stem.script.*.wav files in stems/script/.
    """
    out = []
    for p in STEMS_SCRIPT_DIR.rglob("*.wav"):
        out.append(p.name)
    return sorted(out)


def load_script_dataset(path: str) -> List[str]:
    """
    Load a JSON file consisting of:
        { "items": ["...", "..."] }
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    data = json.loads(p.read_text())

    items = data.get("items", [])
    return [i for i in items if isinstance(i, str) and i.strip()]


# ───────────────────────────────────────────────
# HIGH-LEVEL PIPELINE
# ───────────────────────────────────────────────
def process_script_dataset(
    dataset_path: str,
    *,
    rotational: bool = False,
) -> Dict[str, Any]:
    """
    Load → generate → summarize.
    """
    items = load_script_dataset(dataset_path)
    results = generate_script_stems_bulk(
        items,
        rotational=rotational,
        dataset_origin=f"scripts/{Path(dataset_path).stem}",
    )

    ok = sum(1 for r in results if r.get("ok"))
    fail = len(results) - ok

    return {
        "dataset": dataset_path,
        "total": len(results),
        "ok": ok,
        "fail": fail,
        "results": results,
    }


# ───────────────────────────────────────────────
# CLI MODE
# ───────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SCRIPT Stem Generator (Hybrid Audio API)"
    )
    parser.add_argument("dataset", help="Path to JSON dataset file")
    parser.add_argument("--rotational", action="store_true")

    args = parser.parse_args()

    summary = process_script_dataset(args.dataset, rotational=args.rotational)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
