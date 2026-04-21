"""Firecrawl API key resolution / storage tests."""

import os
from pathlib import Path

import pytest

from webscraper.firecrawl_key import (
    key_present,
    key_source,
    load_firecrawl_key,
    save_firecrawl_key,
)


def test_load_returns_none_when_nothing_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    monkeypatch.delenv("WEBSCRAPER_FIRECRAWL_KEY", raising=False)
    assert load_firecrawl_key() is None
    assert key_present() is False
    assert key_source() == "none"


def test_env_var_wins_over_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    monkeypatch.setenv("WEBSCRAPER_FIRECRAWL_KEY", "fc-from-env")
    # Also write a file key; env var should take precedence
    save_firecrawl_key("fc-from-file")
    assert load_firecrawl_key() == "fc-from-env"
    assert key_source() == "env var"


def test_file_used_when_env_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    monkeypatch.delenv("WEBSCRAPER_FIRECRAWL_KEY", raising=False)
    path = save_firecrawl_key("fc-from-file")
    assert load_firecrawl_key() == "fc-from-file"
    assert "firecrawl.key" in str(path)
    assert "file" in key_source()


def test_save_writes_chmod_600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    path = save_firecrawl_key("fc-secret")
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_save_rejects_empty_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    with pytest.raises(ValueError):
        save_firecrawl_key("   ")


def test_save_overwrites_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    monkeypatch.delenv("WEBSCRAPER_FIRECRAWL_KEY", raising=False)
    save_firecrawl_key("fc-one")
    save_firecrawl_key("fc-two")
    assert load_firecrawl_key() == "fc-two"


def test_load_skips_comment_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    monkeypatch.delenv("WEBSCRAPER_FIRECRAWL_KEY", raising=False)
    # Save a file that begins with a comment, then the key
    path = Path(os.environ["WEBSCRAPER_HOME"]) / "firecrawl.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# my firecrawl key\nfc-real\n", encoding="utf-8")
    os.chmod(path, 0o600)
    assert load_firecrawl_key() == "fc-real"
