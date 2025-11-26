from config import (
    build_sonic3_payload,
    SONIC3_CONTAINER,
    SONIC3_ENCODING,
    SONIC3_SAMPLE_RATE,
    MODEL_ID,
)

def test_payload_contract_minimal():
    p = build_sonic3_payload("Hello", "voice-123")
    assert p["transcript"] == "Hello"
    assert p["voice"]["mode"] == "id"
    assert p["voice"]["id"] == "voice-123"
    assert p["output_format"]["container"] == SONIC3_CONTAINER
    assert p["output_format"]["encoding"] == SONIC3_ENCODING
    assert p["output_format"]["sample_rate"] == SONIC3_SAMPLE_RATE
    assert p["model_id"] == MODEL_ID
