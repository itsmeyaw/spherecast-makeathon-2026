import subprocess
import sys


def test_research_cli_missing_args():
    result = subprocess.run(
        [sys.executable, "scripts/research.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_research_cli_help():
    result = subprocess.run(
        [sys.executable, "scripts/research.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--product-sku" in result.stdout
    assert "--original" in result.stdout
