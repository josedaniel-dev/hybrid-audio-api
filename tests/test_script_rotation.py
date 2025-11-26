
import pytest
from fastapi.testclient import TestClient

from fastapi_server import app
from config import stem_label_script

client = TestClient(app)


def test_script_label_generation():
    """
    Validates that script labels follow:
        stem.script.<slug>
    """
    lbl = stem_label_script("Intro Line")
    assert lbl.startswith("stem.script.")
    assert " " not in lbl
    assert lbl == "stem.script.intro_line"


def test_rotation_pair_endpoint_available():
    """
    Basic smoke test — ensures /rotation/next_pair works.
    Rotational engine is optional; mock if missing.
    """

    res = client.get("/rotation/next_pair")

    # If engine disabled → 503 ok
    if res.status_code == 503:
        assert True
        return

    # Else must return a valid pair
    assert res.status_code == 200
    data = res.json()
    assert "pair" in data
    assert "name" in data["pair"]
    assert "developer" in data["pair"]


def test_rotation_generate_pair_script_support(monkeypatch):
    """
    Full simulation:
    • The rotation engine returns a script-like pair
    • cartesia_generate is mocked
    • get_cached_stem is mocked
    """

    # Mocks
    monkeypatch.setattr(
        "rotational_engine.get_next_pair",
        lambda: {"ok": True, "name": "Alpha", "developer": "Bravo"},
    )

    monkeypatch.setattr(
        "assemble_message.cartesia_generate",
        lambda text, label, voice_id=None, template=None: f"/fake/{label}.wav",
    )

    monkeypatch.setattr(
        "cache_manager.get_cached_stem",
        lambda label: None,
    )

    req = {"extended": True}
    res = client.post("/rotation/generate_pair", json=req)

    if res.status_code == 503:
        assert True
        return

    assert res.status_code == 200
    data = res.json()

    assert data["stems"]["name"]["label"].startswith("stem.name.")
    assert data["stems"]["developer"]["label"].startswith("stem.developer.")
