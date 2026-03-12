import subprocess
import sys
from pathlib import Path


def test_validate_spec_parity_script_runs_cleanly():
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "validate_spec_parity.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Spec parity validation passed." in result.stdout
