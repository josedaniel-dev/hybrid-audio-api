# Tests for /cache/verify_and_repair

def test_verify_and_repair_endpoint(client):
    """
    Ensures the endpoint exists and returns a valid JSON structure.
    """
    response = client.post("/cache/verify_and_repair")
    assert response.status_code == 200

    data = response.json()

    assert "results" in data
    assert "summary" in data
