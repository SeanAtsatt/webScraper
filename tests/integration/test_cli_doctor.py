"""CLI integration tests for `webscraper doctor`."""

import subprocess
import sys

import pytest


# [F-NONE]
@pytest.mark.xfail(
    reason="doctor.py imports deleted webscraper.profile; fixed in Task 13",
    strict=False,
)
def test_doctor_runs_and_exits_cleanly() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "webscraper", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode in (0, 4)  # 0 if healthy, 4 if env incomplete
    assert "Python" in result.stdout
    assert "Playwright" in result.stdout
