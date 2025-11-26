import subprocess, sys

def test_cli_help_runs():
    code = subprocess.call([sys.executable,"CLI.py","--help"])
    assert code == 0
