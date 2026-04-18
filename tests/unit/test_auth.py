"""Auth storage module tests."""

import os
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


def test_list_sessions_empty_when_dir_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import list_sessions

    assert list_sessions() == []


def test_list_sessions_reports_cookie_counts_and_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import list_sessions, save_state

    state = {
        "cookies": [
            # Session-scoped (no expires):
            {"name": "s1", "value": "x", "domain": ".ex.com", "path": "/"},
            # Persistent cookies:
            {
                "name": "p1",
                "value": "x",
                "domain": ".ex.com",
                "path": "/",
                "expires": 2000000000.0,
            },  # 2033
            {
                "name": "p2",
                "value": "x",
                "domain": ".ex.com",
                "path": "/",
                "expires": 1900000000.0,
            },  # 2030
        ],
        "origins": [],
    }
    save_state("ex.com", state)
    summaries = list_sessions()
    assert len(summaries) == 1
    s = summaries[0]
    assert s.domain == "ex.com"
    assert s.cookie_count == 3
    assert s.earliest_session_expiry is not None
    # Earliest future expiry is p2 (2030)
    assert s.earliest_session_expiry.year == 2030
    assert s.file_mode == 0o600


def test_list_sessions_earliest_expiry_none_when_only_session_cookies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import list_sessions, save_state

    save_state(
        "a.com",
        {"cookies": [{"name": "s", "value": "x", "domain": ".a.com", "path": "/"}], "origins": []},
    )
    summaries = list_sessions()
    assert summaries[0].earliest_session_expiry is None


def test_list_sessions_skips_malformed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import auth_dir, list_sessions

    auth_dir().mkdir(parents=True, exist_ok=True)
    (auth_dir() / "broken.json").write_text("not json", encoding="utf-8")
    os.chmod(auth_dir() / "broken.json", 0o600)  # still chmod 600 but malformed content
    summaries = list_sessions()
    # broken entry surfaces with cookie_count=-1 to signal "malformed"
    assert any(s.domain == "broken" and s.cookie_count == -1 for s in summaries)
