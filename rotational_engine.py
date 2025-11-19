"""
rotational_engine.py — Rotational Name/Developer Manager

v5.0 NDF — Dataset-Aware Fair Rotation + Hooks + Extended Stats

Changes in this version:
• Keeps fair round-robin rotation (least-used, then oldest last_used)
• Fully compatible with Sonic-3 + new cartesia_generate() hook contract
• Uses .env/.config-backed COMMON_NAMES_FILE and DEVELOPER_NAMES_FILE
• Extends rotation_stats() with dataset-aware metrics (used/unused/disabled)
• Adds NDF-safe helpers for future CLI/UI control (soft-disable/enable-ready)
"""

import json
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from config import (
    DATA_DIR,
    COMMON_NAMES_FILE,
    DEVELOPER_NAMES_FILE,
    ROTATIONS_META_FILE,
    DEBUG,
)

# Ensure dirs
DATA_DIR.mkdir(exist_ok=True)

# Bootstrap meta file
if not ROTATIONS_META_FILE.exists():
    ROTATIONS_META_FILE.write_text(
        json.dumps(
            {
                "names": {},
                "developers": {},
                "_meta": {
                    "total_names": 0,
                    "total_developers": 0,
                    "last_update": None,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def _ts() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _load_json(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# -------------------------------------------------------
# Dataset loading (backed by external upload_base)
# -------------------------------------------------------
def load_names_dataset() -> List[str]:
    data = _load_json(Path(COMMON_NAMES_FILE))
    items = data.get("items", [])
    # Datasets are already normalized by routes/external, but we strip again defensively
    return [str(x).strip() for x in items if str(x).strip()]


def load_developers_dataset() -> List[str]:
    data = _load_json(Path(DEVELOPER_NAMES_FILE))
    items = data.get("items", [])
    return [str(x).strip() for x in items if str(x).strip()]


# -------------------------------------------------------
# State persistence
# -------------------------------------------------------
def _load_state() -> dict:
    state = _load_json(ROTATIONS_META_FILE)

    # Auto-repair base structure
    state.setdefault("names", {})
    state.setdefault("developers", {})
    state.setdefault(
        "_meta",
        {"total_names": 0, "total_developers": 0, "last_update": None},
    )

    return state


def _save_state(state: dict) -> None:
    # Keep _meta in sync with current datasets
    state["_meta"]["total_names"] = len(load_names_dataset())
    state["_meta"]["total_developers"] = len(load_developers_dataset())
    state["_meta"]["last_update"] = _ts()

    _save_json(ROTATIONS_META_FILE, state)


def _ensure_entry(state: dict, category: str, key: str) -> None:
    if key not in state[category]:
        state[category][key] = {
            "use_count": 0,
            "last_used": None,
            "disabled": False,
        }


# -------------------------------------------------------
# Rotation logic
# -------------------------------------------------------
def _select_next(state: dict, category: str, dataset: List[str]) -> Optional[str]:
    """
    Core rotation selector:
      • Ensures all dataset items exist in state
      • Filters out disabled entries
      • Picks least-used, then oldest last_used
    """

    if not dataset:
        if DEBUG:
            print(f"[Rotation] empty dataset → {category}")
        return None

    # Normalize dataset entries defensively
    normalized_dataset = [str(x).strip() for x in dataset if str(x).strip()]

    for item in normalized_dataset:
        _ensure_entry(state, category, item)

    # Only enabled and still-present-in-dataset entries
    candidates = [
        (name, meta)
        for name, meta in state[category].items()
        if name in normalized_dataset and not meta.get("disabled", False)
    ]

    if not candidates:
        if DEBUG:
            print(f"[Rotation] no enabled entries → {category}")
        return None

    # Least used first → then oldest last_used
    candidates.sort(
        key=lambda x: (
            x[1].get("use_count", 0),
            x[1].get("last_used") or "2000-01-01T00:00:00",
        )
    )

    return candidates[0][0]


# -------------------------------------------------------
# Public API — core getters
# -------------------------------------------------------
def get_next_name() -> Optional[str]:
    dataset = load_names_dataset()
    state = _load_state()

    nxt = _select_next(state, "names", dataset)

    if nxt:
        state["names"][nxt]["use_count"] += 1
        state["names"][nxt]["last_used"] = _ts()
        _save_state(state)

    return nxt


def get_next_developer() -> Optional[str]:
    dataset = load_developers_dataset()
    state = _load_state()

    nxt = _select_next(state, "developers", dataset)

    if nxt:
        state["developers"][nxt]["use_count"] += 1
        state["developers"][nxt]["last_used"] = _ts()
        _save_state(state)

    return nxt


def get_next_pair() -> Dict[str, Any]:
    name = get_next_name()
    dev = get_next_developer()
    return {
        "ok": bool(name and dev),
        "name": name,
        "developer": dev,
        "timestamp": _ts(),
    }


# -------------------------------------------------------
# Reset / soft-reset helpers
# -------------------------------------------------------
def reset_rotation(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Hard reset of rotation counters.

    category:
        None          → reset both
        "names"       → reset only names
        "developers"  → reset only developers
    """
    state = _load_state()

    if category is None:
        state = {"names": {}, "developers": {}, "_meta": state["_meta"]}
    elif category == "names":
        state["names"] = {}
    elif category == "developers":
        state["developers"] = {}

    _save_state(state)

    return {"ok": True, "category": category or "both", "timestamp": _ts()}


# -------------------------------------------------------
# Hooks (used by assemble_message.cartesia_generate)
# -------------------------------------------------------
def pre_tts_hook(text: str, stem_name: str, **kwargs):
    """
    Correct signature:
        cartesia_generate(text, stem_name, ...)

    v5.0:
        • Does not mutate stem_name
        • Returns text as-is (Sonic-3 contract: raw text only)
        • Ready for future personalization logic (e.g., adding context)
    """
    return text, stem_name


def post_tts_hook(stem_name: str, text: str, path: str, **kwargs):
    """
    Post-generation hook.

    v5.0:
        • Currently no-op (reserved for future metrics / external sync)
        • Kept for backward compatibility and extensibility
    """
    return None


# -------------------------------------------------------
# Stats (extended in v5.0)
# -------------------------------------------------------
def _build_category_stats(category: str, dataset: List[str], state: dict) -> dict:
    """
    Internal helper to compute richer stats for a category.
    """
    entries = state.get(category, {})

    total_items = len(dataset)
    enabled = 0
    disabled = 0
    used = 0
    unused = 0

    for item in dataset:
        meta = entries.get(item)
        if not meta:
            unused += 1
            continue

        if meta.get("disabled", False):
            disabled += 1
        else:
            enabled += 1

        if meta.get("use_count", 0) > 0:
            used += 1
        else:
            unused += 1

    return {
        "total_items": total_items,
        "enabled": enabled,
        "disabled": disabled,
        "used_at_least_once": used,
        "never_used": unused,
        "entries": entries,
    }


def rotation_stats() -> dict:
    """
    Extended stats for CLI/UI/monitoring.

    Returns:
        {
          "ok": True,
          "names": { ... per-entry ... },
          "developers": { ... per-entry ... },
          "names_stats": { ... aggregate ... },
          "developers_stats": { ... aggregate ... },
          "_meta": { ... },
          "timestamp": "...",
        }
    """
    state = _load_state()
    names_dataset = load_names_dataset()
    devs_dataset = load_developers_dataset()

    names_stats = _build_category_stats("names", names_dataset, state)
    devs_stats = _build_category_stats("developers", devs_dataset, state)

    return {
        "ok": True,
        "names": state.get("names", {}),
        "developers": state.get("developers", {}),
        "names_stats": names_stats,
        "developers_stats": devs_stats,
        "_meta": state.get("_meta", {}),
        "timestamp": _ts(),
    }


# -------------------------------------------------------
# Self-test
# -------------------------------------------------------
if __name__ == "__main__":
    print("🔁 Testing rotational engine…")
    print("Pair:", get_next_pair())
    print("Stats:", json.dumps(rotation_stats(), indent=2))
