# Tests for /cache/check_many
# Ensures the endpoint responds with a structured matrix.


import json

def test_check_many_endpoint(client):
    """
    Validates that /cache/check_many returns a structured response
    with the 'results' and 'summary' fields.
    """
    response = client.get("/cache/check_many?labels=stem.name.john,stem.developer.maria")
    assert response.status_code == 200

    data = response.json()
    assert "results" in data
    assert "summary" in data

    assert isinstance(data["results"], dict)
    assert "total" in data["summary"]
    assert "gcs_hits" in data["summary"]
    assert "missing" in data["summary"]
