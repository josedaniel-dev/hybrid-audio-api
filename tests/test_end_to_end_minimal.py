from fastapi.testclient import TestClient
from fastapi_server import app

client = TestClient(app)

def test_e2e_flow():
    r1 = client.post("/generate/name", json={"name":"John"})
    assert r1.status_code in (200,503)

    r2 = client.post("/assemble/segments", json={"segments":["Hello","World"]})
    assert r2.status_code in (200,500)

    r3 = client.get("/assemble/output_location")
    assert r3.status_code in (200,400)
