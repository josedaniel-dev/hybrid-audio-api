import tempfile
from pathlib import Path

from cache_manager import (
    register_stem,
    get_cached_stem,
    load_index,
)
from config import resolve_structured_stem_path


def test_cache_register_and_load():
    """
    Updated for v5.2 Hybrid Audio API:
    • uses structured stem labels
    • validates correct resolution of paths
    • ensures cache index stores structured paths
    """

    # canonical label for test
    label = "stem.script.test_key"

    # structured local path where stem would naturally live
    structured_path = resolve_structured_stem_path(label)

    # create fake wav file where it is expected to live
    structured_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

        # Move file into correct structure expected by resolver
        tmp_final = structured_path
        tmp_final.write_bytes(tmp_path.read_bytes())

        # Register stem into cache
        register_stem(label, "Hello world", str(tmp_final))

    # Retrieve via cache
    cached = get_cached_stem(label)
    assert isinstance(cached, str), "Cached path should be a string"
    assert cached.endswith(".wav"), "Cached file should be a wav path"

    # Validate index state
    index = load_index()
    assert "stems" in index, "Index must contain stems section"
    assert label in index["stems"], "Label must be stored in index"

    # Check structured path exists
    assert Path(cached).exists(), "Cached stem file should exist in filesystem"
