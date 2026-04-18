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


# [F-REQ-016]
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


# [F-REQ-019]
def test_auth_list_reports_saved_session(fixture_server: str, ws_home: Path) -> None:
    _run(
        "login",
        f"{fixture_server}/auth/login",
        env_extra={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    result = _run("auth", "list", env_extra={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert "127.0.0.1" in result.stdout or "127.0.0.1" in result.stderr


# [F-REQ-020]
def test_auth_forget_deletes_saved_session(fixture_server: str, ws_home: Path) -> None:
    _run(
        "login",
        f"{fixture_server}/auth/login",
        env_extra={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    assert (ws_home / "auth").glob("*.json")
    result = _run("auth", "forget", "127.0.0.1", env_extra={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert not list((ws_home / "auth").glob("*.json"))


# [F-REQ-020]
def test_auth_prune_removes_session_only_files(ws_home: Path) -> None:
    # Pre-seed two fake auth files directly
    (ws_home / "auth").mkdir(parents=True)
    (ws_home / "auth" / "keep.com.json").write_text(
        '{"cookies": [{"name":"p","value":"x","domain":".keep.com","path":"/"'
        ',"expires": 9999999999.0}], "origins": []}',
    )
    (ws_home / "auth" / "drop.com.json").write_text(
        '{"cookies": [{"name":"s","value":"x","domain":".drop.com","path":"/"}], "origins": []}',
    )
    import os as _os

    _os.chmod(ws_home / "auth" / "keep.com.json", 0o600)
    _os.chmod(ws_home / "auth" / "drop.com.json", 0o600)

    result = _run("auth", "prune", env_extra={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert (ws_home / "auth" / "keep.com.json").exists()
    assert not (ws_home / "auth" / "drop.com.json").exists()
