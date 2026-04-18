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
