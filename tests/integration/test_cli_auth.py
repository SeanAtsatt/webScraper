"""CLI tests for login / auth subcommands."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(
    *args: str, env_extra: dict[str, str] | None = None, stdin_input: str = ""
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        input=stdin_input,
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )


@pytest.fixture
def ws_home(tmp_path: Path) -> Path:
    return tmp_path / "wshome"


def test_login_saves_storage_state(fixture_server: str, ws_home: Path) -> None:
    # Use /auth/login so the fixture server sets a persistent cookie during the
    # interactive session; the test simulates "user pressed Enter" via stdin.
    result = _run(
        "login",
        f"{fixture_server}/auth/login",
        env_extra={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # Fixture host is 127.0.0.1 — saved under that key (IP fallback path)
    saved = list((ws_home / "auth").glob("*.json"))
    assert len(saved) == 1
    state = json.loads(saved[0].read_text())
    assert any(c.get("name") == "fixture_auth" for c in state["cookies"])
