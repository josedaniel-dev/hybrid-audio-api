# tests/conftest.py
import sys
from pathlib import Path

# Fuerza a pytest a importar desde el root real del proyecto.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import pytest
from fastapi.testclient import TestClient
from fastapi_server import app

@pytest.fixture
def client():
    return TestClient(app)
