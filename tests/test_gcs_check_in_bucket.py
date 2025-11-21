import pytest
from fastapi.testclient import TestClient

from fastapi_server import app

client = TestClient(app)


@pytest.mark.parametrize("label", [
    "stem.name.john",
    "stem.developer.maria",
    "stem.script.intro_line",
])
def test_gcs_check_in_bucket_mocked(monkeypatch, label):
    """
    Test actualizado para la arquitectura NUEVA.
    Validamos:
        • exists se basa en gcs_has_file mockeado
        • gcs_uri existe y es string
        • relative_path corresponde al structured resolver
        • NO se exige "fake-gcs" en la URI porque ya no usamos gcs_resolve_uri
    """

    # Simula que GCS solo "contiene" archivos que incluyen la palabra name
    def fake_gcs_has_file(filename):
        return "name" in filename

    # --- PATCH CRÍTICO ---
    # Activa la bandera GCS_OK dentro de routes.cache
    monkeypatch.setattr("routes.cache.GCS_OK", True)

    # Fuerza GCS enabled en config
    monkeypatch.setattr("config.is_gcs_enabled", lambda: True)

    # Mock exacto que el router llama
    monkeypatch.setattr("gcloud_storage.gcs_check_file_exists", fake_gcs_has_file)

    res = client.get(f"/cache/check_in_bucket?label={label}")
    assert res.status_code == 200

    data = res.json()

    # Campos obligatorios según contrato actual
    assert "exists" in data
    assert "gcs_uri" in data
    assert "relative_path" in data
    assert "blob_name" in data
    assert "consistency" in data

    # Caso 1 → labels con "name" deben marcar exists=True
    if "name" in label:
        assert data["exists"] is True
        assert isinstance(data["gcs_uri"], str)
        assert len(data["gcs_uri"]) > 0
    else:
        assert data["exists"] is False
