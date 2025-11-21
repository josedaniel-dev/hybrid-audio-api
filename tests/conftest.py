# tests/conftest.py
import sys
from pathlib import Path

# Fuerza a pytest a importar desde el root real del proyecto.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
