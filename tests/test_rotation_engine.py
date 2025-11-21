from fastapi.testclient import TestClient
from fastapi_server import app

client = TestClient(app)

def test_rotation_endpoints():
    for ep in ("/rotation/next_name","/rotation/next_developer","/rotation/next_pair"):
        r = client.get(ep)
        assert r.status_code in (200,503)
