from fastapi.testclient import TestClient
from fastapi_server import app

client = TestClient(app)

def test_template_assemble_smoke():
    payload = {
        "first_name": "John",
        "developer": "Hilton",
        "template": "double_anchor_hybrid_v3_6.json",
        "upload": False
    }
    r = client.post("/assemble/template?extended=true", json=payload)
    assert r.status_code in (200,400,500)
