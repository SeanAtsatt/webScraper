"""CLI integration tests for `webscraper doctor`."""

import os
import subprocess
import sys
from pathlib import Path


def test_doctor_runs_and_reports_known_checks(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "webscraper", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "WEBSCRAPER_HOME": str(tmp_path / "wshome")},
    )
    # Exit 0 if healthy, 4 if any check failed (playwright may be missing in some envs)
    assert result.returncode in (0, 4)
    assert "Python" in result.stdout
    assert "Playwright" in result.stdout
    assert "auth dir" in result.stdout.lower() or "saved sessions" in result.stdout.lower()
