from cartesia_client import _validate_wav_bytes
import pytest
import io, wave

def make_wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(b"\x00\x00"*48000)
    return buf.getvalue()

def test_wav_validation_accepts_valid():
    _validate_wav_bytes(make_wav())

def test_wav_validation_rejects_non_wav():
    with pytest.raises(Exception):
        _validate_wav_bytes(b"xxx")
