"""--auto-out path resolution tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from webscraper.out import resolve_auto_out, slugify


# [F-NONE]
def test_slugify_lowercases_and_replaces_nonalnum() -> None:
    assert slugify("Hello World!") == "hello-world-"
    assert slugify("Foo_Bar") == "foo-bar"


# [F-NONE]
def test_slugify_truncates_long_input() -> None:
    assert slugify("a" * 200) == "a" * 64


# [F-NONE]
def test_slugify_empty_input_returns_index() -> None:
    assert slugify("") == "index"


# [F-REQ-021]
def test_resolve_auto_out_uses_ai_working_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    (project / "ai_working").mkdir(parents=True)
    (project / "sub").mkdir()
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    path = resolve_auto_out(
        url="https://www.connectance.org/home",
        render_format="json",
        cwd=project / "sub",
        now=now,
    )
    assert (
        path
        == project / "ai_working" / "scraped" / "connectance.org" / "2026-04-16T18-30-00Z-home.json"
    )


# [F-REQ-021]
def test_resolve_auto_out_falls_back_to_webscraper_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    bare = tmp_path / "bare"
    bare.mkdir()
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    path = resolve_auto_out(
        url="https://www.connectance.org/home",
        render_format="json",
        cwd=bare,
        now=now,
    )
    assert (
        path == tmp_path / "wshome" / "out" / "connectance.org" / "2026-04-16T18-30-00Z-home.json"
    )


# [F-REQ-021]
def test_resolve_auto_out_uses_render_format_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    assert (
        resolve_auto_out(
            "https://ex.com/",
            render_format="markdown",
            cwd=tmp_path,
            now=now,
        ).suffix
        == ".md"
    )
    assert (
        resolve_auto_out(
            "https://ex.com/",
            render_format="html",
            cwd=tmp_path,
            now=now,
        ).suffix
        == ".html"
    )


# [F-REQ-021]
def test_resolve_auto_out_empty_path_becomes_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    path = resolve_auto_out(
        url="https://example.com/",
        render_format="json",
        cwd=tmp_path,
        now=now,
    )
    assert path.name == "2026-04-16T18-30-00Z-index.json"


# [F-NONE]
def test_resolve_crawl_root_under_ai_working(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from webscraper.out import resolve_crawl_root

    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    project = tmp_path / "proj"
    (project / "ai_working").mkdir(parents=True)
    now = datetime(2026, 4, 19, 14, 0, 0, tzinfo=UTC)
    root = resolve_crawl_root(
        seed="https://www.connectance.org/home",
        cwd=project,
        now=now,
    )
    assert root == project / "ai_working" / "scraped" / "connectance.org" / "2026-04-19T14-00-00Z"


# [F-NONE]
def test_resolve_crawl_root_falls_back_to_webscraper_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from webscraper.out import resolve_crawl_root

    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    bare = tmp_path / "bare"
    bare.mkdir()
    now = datetime(2026, 4, 19, 14, 0, 0, tzinfo=UTC)
    root = resolve_crawl_root(seed="https://www.ex.com/", cwd=bare, now=now)
    assert root == tmp_path / "wshome" / "out" / "ex.com" / "2026-04-19T14-00-00Z"


# [F-NONE]
def test_slugify_for_url_produces_collision_free_slug_per_run(tmp_path: Path) -> None:
    from webscraper.out import slugify_for_url

    s1 = slugify_for_url("https://ex.com/a/b/page")
    s2 = slugify_for_url("https://ex.com/a/b/page")  # same URL → same slug
    s3 = slugify_for_url("https://ex.com/a/b/page?x=1")  # different query → different slug
    assert s1 == s2
    assert s1 != s3
