# tests/test_cartesia_generate_signature.py

import ast
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "assemble_message.py"


def test_cartesia_generate_imports_sonic3_builder():
    """
    Verifica que assemble_message.py importa build_sonic3_payload desde config.
    """
    with open(TARGET, "r", encoding="utf8") as f:
        tree = ast.parse(f.read(), str(TARGET))

    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "config":
            for alias in node.names:
                if alias.name == "build_sonic3_payload":
                    found = True

    assert found, "assemble_message.py debe importar build_sonic3_payload"
