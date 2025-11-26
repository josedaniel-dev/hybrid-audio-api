from config import CARTESIA_API_URL

def test_cartesia_endpoint_looks_valid():
    assert "api.cartesia.ai" in CARTESIA_API_URL
    assert "tts" in CARTESIA_API_URL
    assert "bytes" in CARTESIA_API_URL
