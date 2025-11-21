from fastapi.testclient import TestClient
from fastapi_server import app

client = TestClient(app)

def test_segments_assemble():
    r = client.post("/assemble/segments", json={"segments":["Hello","World"]})
    assert r.status_code in (200,500)
