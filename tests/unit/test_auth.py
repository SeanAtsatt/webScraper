"""Auth storage module tests."""

from pathlib import Path

import pytest

from webscraper.auth import auth_dir, auth_file_for, registrable_domain
from webscraper.errors import UsageError


def test_registrable_domain_strips_subdomains() -> None:
    assert registrable_domain("https://www.connectance.org/home") == "connectance.org"
    assert registrable_domain("https://app.notion.so/workspace") == "notion.so"


def test_registrable_domain_handles_multilevel_tlds() -> None:
    assert registrable_domain("https://user.github.io/repo") == "user.github.io"
    assert registrable_domain("https://www.example.co.uk/path") == "example.co.uk"


def test_registrable_domain_raises_on_ip_or_localhost() -> None:
    with pytest.raises(UsageError):
        registrable_domain("http://127.0.0.1:8080/")
    with pytest.raises(UsageError):
        registrable_domain("http://localhost/")


def test_auth_file_for_returns_path_under_auth_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    path = auth_file_for("https://www.connectance.org/home")
    assert path == tmp_path / "auth" / "connectance.org.json"


def test_auth_dir_returns_auth_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    assert auth_dir() == tmp_path / "auth"


def test_save_state_writes_chmod_600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import save_state

    path = save_state("example.com", {"cookies": [], "origins": []})
    assert path == tmp_path / "auth" / "example.com.json"
    assert path.exists()
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_save_state_round_trips_with_load_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import load_state, save_state

    state = {
        "cookies": [
            {
                "name": "sess",
                "value": "abc",
                "domain": ".example.com",
                "path": "/",
                "expires": 9999999999.0,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
        ],
        "origins": [],
    }
    save_state("example.com", state)
    loaded = load_state("example.com")
    assert loaded == state


def test_load_state_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import load_state

    assert load_state("nonexistent.com") is None
