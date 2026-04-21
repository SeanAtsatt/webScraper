"""FirecrawlFetcher unit tests against the mock endpoint."""

import pytest

from webscraper.errors import EnvironmentError, FetcherError
from webscraper.fetch.base import FetchOptions
from webscraper.fetch.firecrawl import FirecrawlFetcher


def _mock_api_base(fixture_server: str) -> str:
    # FirecrawlFetcher appends "/v1/scrape"; mock lives at "<server>/firecrawl/v1/scrape"
    return f"{fixture_server}/firecrawl"


# [F-NONE]
def test_raises_when_key_missing(fixture_server: str) -> None:
    f = FirecrawlFetcher(api_base=_mock_api_base(fixture_server))
    opts = FetchOptions(allow_paid=True, firecrawl_api_key=None)
    with pytest.raises(EnvironmentError):
        f.fetch("https://ex.com/", opts)


# [F-NONE]
def test_happy_path_returns_html_and_metadata(fixture_server: str) -> None:
    f = FirecrawlFetcher(api_base=_mock_api_base(fixture_server))
    opts = FetchOptions(allow_paid=True, firecrawl_api_key="fc-test")
    result = f.fetch("https://ex.com/home", opts)
    assert result.http_status == 200
    assert "Firecrawl: https://ex.com/home" in result.html
    assert result.final_url == "https://ex.com/home"


# [F-NONE]
def test_402_maps_to_environment_error(fixture_server: str) -> None:
    f = FirecrawlFetcher(api_base=_mock_api_base(fixture_server))
    opts = FetchOptions(allow_paid=True, firecrawl_api_key="fc-test")
    with pytest.raises(EnvironmentError) as exc:
        f.fetch("https://ex.com/force-402", opts)
    assert "credits" in str(exc.value).lower() or "payment" in str(exc.value).lower()


# [F-NONE]
def test_429_maps_to_fetcher_error(fixture_server: str) -> None:
    f = FirecrawlFetcher(api_base=_mock_api_base(fixture_server))
    opts = FetchOptions(allow_paid=True, firecrawl_api_key="fc-test")
    with pytest.raises(FetcherError) as exc:
        f.fetch("https://ex.com/force-429", opts)
    assert exc.value.reason == "firecrawl_rate_limited"


# [F-NONE]
def test_500_maps_to_fetcher_error(fixture_server: str) -> None:
    f = FirecrawlFetcher(api_base=_mock_api_base(fixture_server))
    opts = FetchOptions(allow_paid=True, firecrawl_api_key="fc-test")
    with pytest.raises(FetcherError) as exc:
        f.fetch("https://ex.com/force-500", opts)
    assert exc.value.reason == "firecrawl_server_error"


# [F-NONE]
def test_401_bad_key_maps_to_environment_error(fixture_server: str) -> None:
    f = FirecrawlFetcher(api_base=_mock_api_base(fixture_server))
    # The mock returns 401 if Authorization header is missing/malformed;
    # we simulate a "bad key" by sending a key the mock won't accept —
    # but the mock accepts ANY Bearer token, so we override the header
    # by passing an empty key (goes through as "Bearer " → 401 reject).
    opts = FetchOptions(allow_paid=True, firecrawl_api_key="")
    with pytest.raises(EnvironmentError):
        f.fetch("https://ex.com/", opts)
