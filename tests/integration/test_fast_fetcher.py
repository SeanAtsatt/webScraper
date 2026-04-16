"""FastFetcher integration tests against the fixture server."""

import pytest

from webscraper.errors import RedirectLoopError, TooLargeError
from webscraper.fetch.base import FetchOptions
from webscraper.fetch.fast import FastFetcher


def test_fast_fetcher_retrieves_static_page(fixture_server: str) -> None:
    f = FastFetcher()
    result = f.fetch(f"{fixture_server}/static/article", FetchOptions())
    assert result.http_status == 200
    assert "Static Article" in result.html
    assert result.final_url.endswith("/static/article")
    assert result.elapsed_ms >= 0


def test_fast_fetcher_raises_on_redirect_loop(fixture_server: str) -> None:
    f = FastFetcher()
    with pytest.raises(RedirectLoopError):
        f.fetch(f"{fixture_server}/redirect-loop", FetchOptions())


def test_fast_fetcher_raises_on_oversize(fixture_server: str) -> None:
    f = FastFetcher()
    with pytest.raises(TooLargeError):
        f.fetch(f"{fixture_server}/oversize", FetchOptions(max_body_bytes=1_000_000))
