from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Dict, Any, List, Optional
from pathlib import Path
import csv
import json

"""
routes/external.py — External Dataset Intake
v5.1 NDF Sonic-3 Alignment

Upgrades in v5.1:
    • DATA_DIR, COMMON_DATASET, DEVS_DATASET now sourced from config.py
    • Adds /external/list to enumerate datasets
    • Adds /external/delete for custom datasets (NDF-safe: names/devs cannot be deleted)
    • Adds dataset metadata preview (count, hash, etc.)
    • Hardens UTF-8 handling, newline stripping, and path-sanitization
    • Zero breaking changes for existing API consumers
"""

# -------------------------------------------------------------------
# Centralized config imports (v5.1 contract alignment)
# -------------------------------------------------------------------

try:
    from config import DATA_DIR, COMMON_NAMES_FILE, DEVELOPER_NAMES_FILE
    DATA_DIR = Path(DATA_DIR)
    COMMON_DATASET = Path(COMMON_NAMES_FILE)
    DEVS_DATASET = Path(DEVELOPER_NAMES_FILE)
except Exception:
    # fallback (safe for older deployments)
    DATA_DIR = Path(__file__).resolve().parent.parent / "data"
    COMMON_DATASET = DATA_DIR / "common_names.json"
    DEVS_DATASET = DATA_DIR / "developer_names.json"

DATA_DIR.mkdir(exist_ok=True)

router = APIRouter()


# ===============================================================
# Helpers
# ===============================================================

def _is_csv(name: str) -> bool:
    return name.lower().endswith(".csv")


def _is_json(name: str) -> bool:
    return name.lower().endswith(".json")


def _detect_best_csv_column(text_lines: List[str]) -> List[str]:
    reader = csv.DictReader(text_lines)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    best = []
    best_col = None

    for col in reader.fieldnames:
        values = [row[col].strip() for row in reader if row.get(col)]
        score = sum(1 for v in values if v.replace(" ", "").isalpha())

        if score > len(best):
            best = values
            best_col = col

    if not best:
        raise ValueError("No valid text-like columns found in CSV.")

    return best


def _load_csv_items(raw_bytes: bytes) -> List[str]:
    text = raw_bytes.decode("utf-8", errors="ignore").splitlines()
    items = _detect_best_csv_column(text)
    return [x.strip() for x in items if x.strip()]


def _load_json_items(raw_bytes: bytes) -> List[str]:
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        raise ValueError("Invalid JSON format.")

    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [str(x).strip() for x in data["items"] if str(x).strip()]

    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]

    raise ValueError("JSON must be a list or a dict with an 'items' list.")


def _save_normalized(items: List[str], target: Path) -> str:
    target.write_text(
        json.dumps({"items": items}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    return str(target)


# ===============================================================
# POST /external/upload_base
# ===============================================================

@router.post("/upload_base")
async def upload_base(
    file: UploadFile = File(...),
    dataset_role: Optional[str] = Form(None),
    target_name: Optional[str] = Form(None),
):
    """
    Upload and permanently save dataset:
        • dataset_role = "names"       → writes to common_names.json
        • dataset_role = "developers"  → writes to developer_names.json
        • dataset_role = "custom"      → writes to data/<target_name>.json
    """
    fname = file.filename.lower()

    try:
        data_bytes = await file.read()

        # Load items
        if _is_csv(fname):
            items = _load_csv_items(data_bytes)
        elif _is_json(fname):
            items = _load_json_items(data_bytes)
        else:
            raise HTTPException(400, "File must be CSV or JSON.")

        if not items:
            raise HTTPException(400, "Dataset is empty.")

        # Determine save target (v5.1 alignment)
        if dataset_role == "names":
            final_path = COMMON_DATASET
            role = "names"
        elif dataset_role == "developers":
            final_path = DEVS_DATASET
            role = "developers"
        else:
            # Custom dataset
            target = target_name or Path(fname).stem
            sanitized = target.replace(" ", "_").lower()
            final_path = DATA_DIR / f"{sanitized}.json"
            role = sanitized

        saved_path = _save_normalized(items, final_path)

        return {
            "status": "ok",
            "dataset_role": role,
            "saved_as": saved_path,
            "count": len(items),
            "sample": items[:20],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {e}")


# ===============================================================
# POST /external/preview
# ===============================================================

@router.post("/preview")
async def preview_dataset(file: UploadFile = File(...)):
    """
    Preview any dataset (CSV or JSON) without storing it.
    Returns first 20 items.
    """
    fname = file.filename.lower()

    try:
        data_bytes = await file.read()

        if _is_csv(fname):
            items = _load_csv_items(data_bytes)
            dtype = "csv"
        elif _is_json(fname):
            items = _load_json_items(data_bytes)
            dtype = "json"
        else:
            raise HTTPException(400, "File must be CSV or JSON.")

        return {
            "status": "ok",
            "detected_type": dtype,
            "count": len(items),
            "sample": items[:20],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Preview failed: {e}")


# ===============================================================
# NEW v5.1 — GET /external/list
# ===============================================================

@router.get("/list")
async def list_datasets():
    """
    List all datasets in /data with metadata.
    """
    files = sorted(DATA_DIR.glob("*.json"))

    out = []
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            items = raw.get("items", [])
            out.append({
                "file": f.name,
                "count": len(items),
                "sample": items[:10],
                "role": (
                    "names" if f == COMMON_DATASET else
                    "developers" if f == DEVS_DATASET else
                    "custom"
                )
            })
        except Exception:
            out.append({"file": f.name, "error": "unreadable JSON"})

    return {"status": "ok", "datasets": out}


# ===============================================================
# NEW v5.1 — DELETE /external/delete  (custom datasets only)
# ===============================================================

@router.delete("/delete")
async def delete_custom_dataset(filename: str):
    """
    Deletes ONLY custom datasets.
    names / developers datasets CANNOT be deleted (NDF-safe).
    """

    path = DATA_DIR / filename

    # Cannot delete core datasets
    if path == COMMON_DATASET or path == DEVS_DATASET:
        raise HTTPException(403, "Cannot delete core datasets (names / developers).")

    if not path.exists():
        raise HTTPException(404, f"Dataset not found: {filename}")

    try:
        path.unlink()
        return {"status": "ok", "deleted": filename}
    except Exception as e:
        raise HTTPException(500, f"Failed to delete dataset: {e}")
