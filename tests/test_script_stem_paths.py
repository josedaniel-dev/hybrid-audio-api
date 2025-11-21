from pathlib import Path
from config import (
    STEMS_SCRIPT_DIR,
    stem_label_script,
    resolve_structured_stem_path,
)


def test_script_path_resolution():
    """
    SCRIPT stems must be saved to:
        stems/script/stem.script.<slug>.wav
    """
    lbl = stem_label_script("Hello World")

    p = resolve_structured_stem_path(lbl)

    assert isinstance(p, Path)
    assert "script" in str(p)
    assert p.parent == STEMS_SCRIPT_DIR
    assert p.name.endswith(".wav")
    assert p.name.startswith("stem.script.")


def test_script_directory_exists():
    """
    Ensures the directory stems/script exists.
    """
    assert STEMS_SCRIPT_DIR.exists()
    assert STEMS_SCRIPT_DIR.is_dir()
