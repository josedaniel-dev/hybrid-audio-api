"""Helpers for comparing local stems against GCS copies."""

from __future__ import annotations

from pathlib import Path

from config import (
    STEMS_DIR,
    GCS_BUCKET,
    GCS_FOLDER_STEMS,
    is_gcs_enabled,
    build_gcs_blob_path,
)

try:
    from gcloud_storage import init_gcs_client
except Exception:  # pragma: no cover - optional dependency
    init_gcs_client = None  # type: ignore


def local_has_file(stem_filename: str) -> bool:
    """Return True only if the file exists and is a regular file."""
    p = STEMS_DIR / stem_filename
    return p.exists() and p.is_file()


def gcs_has_file(stem_filename: str) -> bool:
    """Return True if the file exists under the configured GCS folder."""
    if not (is_gcs_enabled() and init_gcs_client and GCS_BUCKET):
        return False
    try:
        client = init_gcs_client()
        if not client:
            return False
        bucket = client.bucket(GCS_BUCKET)
        blob_name = build_gcs_blob_path(GCS_FOLDER_STEMS, stem_filename)
        blob = bucket.blob(blob_name)
        return blob.exists()
    except Exception as exc:
        # Do not raise, but warn – aligns with hardened diagnostic patterns.
        print(f"[WARN] gcs_has_file: failed to query GCS for '{stem_filename}': {exc}")
        return False


def compare_local_vs_gcs(stem_filename: str) -> str:
    """Return a high-level consistency status for a given stem filename.

    Possible returns:
        - 'match'
        - 'local_only'
        - 'gcs_only'
        - 'missing'
    """
    local = local_has_file(stem_filename)
    gcs = gcs_has_file(stem_filename)

    if local and gcs:
        return "match"
    if local and not gcs:
        return "local_only"
    if gcs and not local:
        return "gcs_only"
    return "missing"

# ───────────────────────────────────────────────────────────────
# 🌐 v5.2 NDF — Multi-Category Consistency Layer (Aditive)
#     • Adds support for stems/name/, stems/developer/, stems/script/
#     • Adds folder-level auditing vs GCS
#     • Fully backward compatible (flat stems/*.wav still supported)
# ───────────────────────────────────────────────────────────────

def _iter_local_stems() -> dict:
    """
    Returns a mapping of:
        {
            "name": [<files>],
            "developer": [<files>],
            "script": [<files>],
            "flat": [<files>]   # legacy support
        }
    """
    categories = {
        "name": (STEMS_DIR / "name").rglob("*.wav"),
        "developer": (STEMS_DIR / "developer").rglob("*.wav"),
        "script": (STEMS_DIR / "script").rglob("*.wav"),
        "flat": STEMS_DIR.glob("*.wav"),  # old structure
    }

    out = {}
    for cat, it in categories.items():
        out[cat] = sorted([str(p.relative_to(STEMS_DIR)) for p in it])
    return out


def _iter_gcs_stems(prefix: str = GCS_FOLDER_STEMS) -> list[str]:
    """
    Lists blobs from GCS under the given prefix.
    Returns relative blob names (prefix removed).
    """
    if not (is_gcs_enabled() and init_gcs_client and GCS_BUCKET):
        return []

    try:
        client = init_gcs_client()
        if not client:
            return []

        bucket = client.bucket(GCS_BUCKET)

        blobs = bucket.list_blobs(prefix=prefix)
        out = []
        for b in blobs:
            name = b.name
            if name.startswith(prefix + "/"):
                rel = name[len(prefix)+1:]
            else:
                rel = name
            if rel.endswith(".wav"):
                out.append(rel)
        return sorted(out)

    except Exception as exc:
        print(f"[WARN] gcs_consistency: failed listing GCS prefix '{prefix}': {exc}")
        return []


def compare_category(category: str) -> dict:
    """
    Compare a specific category: name / developer / script / flat.

    Output:
    {
        "category": "<category>",
        "local_count": N,
        "gcs_count": M,
        "matches": [...],
        "local_only": [...],
        "gcs_only": [...],
        "missing": [...]   # rarely used here but kept for symmetry
    }
    """
    local = _iter_local_stems().get(category, [])
    gcs = _iter_gcs_stems(prefix=GCS_FOLDER_STEMS)

    # Filter GCS by category prefix (e.g., "name/", "developer/")
    if category in ("name", "developer", "script"):
        local_prefixed = [p for p in local]
        gcs_prefixed = [p for p in gcs if p.startswith(f"{category}/")]
    else:
        local_prefixed = local
        gcs_prefixed = [p for p in gcs if "/" not in p]  # flat only

    local_set = set(local_prefixed)
    gcs_set = set(gcs_prefixed)

    return {
        "category": category,
        "local_count": len(local_prefixed),
        "gcs_count": len(gcs_prefixed),
        "matches": sorted(local_set & gcs_set),
        "local_only": sorted(local_set - gcs_set),
        "gcs_only": sorted(gcs_set - local_set),
        "missing": [],  # placeholder for future extended mode
    }


def summarize_all_categories() -> dict:
    """
    Multi-category consistency audit (local vs GCS).

    Returns:
    {
        "name": {...},
        "developer": {...},
        "script": {...},
        "flat": {...},
        "timestamp": "...",
        "bucket": GCS_BUCKET,
        "gcs_enabled": True/False
    }
    """
    return {
        "name": compare_category("name"),
        "developer": compare_category("developer"),
        "script": compare_category("script"),
        "flat": compare_category("flat"),
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        "bucket": GCS_BUCKET,
        "gcs_enabled": is_gcs_enabled(),
    }


__all__ = [
    "compare_local_vs_gcs",
    "gcs_has_file",
    "local_has_file",
    # new exports:
    "compare_category",
    "summarize_all_categories",
]

# ───────────────────────────────────────────────────────────────
# v5.3 — Category Consistency v2 (additive-only)
#     • Provides compare_category_v2
#     • Provides summarize_all_categories_v2
#     • Fully non-destructive; v1 functions remain untouched
# ───────────────────────────────────────────────────────────────

def compare_category_v2(category: str) -> dict:
    """
    Extended multi-category comparison.
    Returns a consistency report for a given category.

    Output:
    {
        "category": "<category>",
        "local_count": int,
        "gcs_count": int,
        "matches": [...],
        "local_only": [...],
        "gcs_only": [...],
        "missing": [...]
    }
    """

    categories = _iter_local_stems()  # { name: [...], developer: [...], ... }
    local_items = categories.get(category, [])

    # Get ALL remote stems once and filter depending on category
    gcs_all = _iter_gcs_stems(prefix=GCS_FOLDER_STEMS)

    if category in ("name", "developer", "script"):
        gcs_items = [p for p in gcs_all if p.startswith(f"{category}/")]
    elif category == "generic":  # alias for flat, but explicit
        gcs_items = [p for p in gcs_all if "/" not in p]
    else:  # fallback: flat
        gcs_items = [p for p in gcs_all if "/" not in p]

    local_set = set(local_items)
    gcs_set = set(gcs_items)

    # Missing = items that are neither in local nor GCS but exist in theoretical dataset
    # Since we do not have a dataset reference here, we leave it empty.
    missing = []

    return {
        "category": category,
        "local_count": len(local_items),
        "gcs_count": len(gcs_items),
        "matches": sorted(local_set & gcs_set),
        "local_only": sorted(local_set - gcs_set),
        "gcs_only": sorted(gcs_set - local_set),
        "missing": missing,
    }


def summarize_all_categories_v2() -> dict:
    """
    Extended multi-category summary report.
    Includes the five required categories:
        - name
        - developer
        - script
        - generic (alias for flat)
        - flat (legacy)
    
    Output:
    {
        "categories": {
            "name": {...},
            "developer": {...},
            "script": {...},
            "generic": {...},
            "flat": {...}
        },
        "bucket": ...,
        "gcs_enabled": bool,
        "timestamp": "..."
    }
    """

    report = {
        "categories": {
            "name": compare_category_v2("name"),
            "developer": compare_category_v2("developer"),
            "script": compare_category_v2("script"),
            "generic": compare_category_v2("generic"),
            "flat": compare_category_v2("flat"),
        },
        "bucket": GCS_BUCKET,
        "gcs_enabled": is_gcs_enabled(),
        "timestamp": __import__("time").strftime(
            "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()
        ),
    }

    return report


# Export the v2 API surface
__all__.extend([
    "compare_category_v2",
    "summarize_all_categories_v2",
])
