from fastapi.testclient import TestClient
from fastapi_server import app

client = TestClient(app)

def test_generate_name_smoke():
    r = client.post("/generate/name", json={"name": "John"})
    assert r.status_code in (200,503)

def test_generate_developer_smoke():
    r = client.post("/generate/developer", json={"developer": "Hilton"})
    assert r.status_code in (200,503)

def test_generate_combined_smoke():
    r = client.post("/generate/combined", json={"name":"John","developer":"Hilton"})
    assert r.status_code in (200,503)
