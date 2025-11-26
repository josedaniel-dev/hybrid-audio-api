# tests/test_sonic3_contract.py

"""
Tests oficiales del contrato Sonic-3 para Hybrid Audio API.
Compatibles con la arquitectura real del proyecto.
No bloquean claves legítimas ni estructuras válidas.
"""

import pytest

# Importación robusta
from config import (
    build_sonic3_payload,
    SONIC3_SAMPLE_RATE,
    SONIC3_CONTAINER,
    SONIC3_ENCODING,
    CARTESIA_API_URL,
    MODEL_ID,
    VOICE_ID,
)


# --------------------------------------------------------------------
# 1. output_format debe cumplir el contrato Sonic-3
# --------------------------------------------------------------------
def test_output_format_contract():
    payload = build_sonic3_payload("hola mundo", voice_id="abc123")

    assert "output_format" in payload, "output_format debe existir"
    out = payload["output_format"]

    assert out["container"] == SONIC3_CONTAINER
    assert out["encoding"] == SONIC3_ENCODING
    assert int(out["sample_rate"]) == int(SONIC3_SAMPLE_RATE)


# --------------------------------------------------------------------
# 2. voice debe cumplir estructura Sonic-3
# --------------------------------------------------------------------
def test_voice_block_format():
    payload = build_sonic3_payload("hola mundo", voice_id="abc123")

    assert "voice" in payload
    voice = payload["voice"]

    assert voice["mode"] == "id"
    assert isinstance(voice["id"], str)
    assert len(voice["id"]) > 0


# --------------------------------------------------------------------
# 3. endpoint debe ser /tts/bytes (NO bloqueamos la substring /tts)
# --------------------------------------------------------------------
def test_no_block_cartesia_endpoints_are_valid():
    assert "tts" in CARTESIA_API_URL, "El endpoint debe incluir /tts"
    assert CARTESIA_API_URL.endswith("bytes"), "Debe terminar en /bytes"


# --------------------------------------------------------------------
# 4. claves como voice_id, model_id NO deben generar falsos positivos
# --------------------------------------------------------------------
def test_nothing_restricts_legit_config_keys():
    assert isinstance(MODEL_ID, str)
    assert isinstance(VOICE_ID, str)
    assert isinstance(SONIC3_SAMPLE_RATE, int)
