"""End-to-end dispatcher integration with the mock Firecrawl endpoint."""

from pathlib import Path
from typing import cast

import pytest

from webscraper.fetch.base import Fetcher, FetchOptions
from webscraper.fetch.browser import BrowserFetcher
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions
from webscraper.fetch.fast import FastFetcher
from webscraper.fetch.firecrawl import FirecrawlFetcher


def _dispatcher_against_mock(fixture_server: str) -> Dispatcher:
    fetchers: list[Fetcher] = cast(
        list[Fetcher],
        [
            FastFetcher(),
            BrowserFetcher(),
            FirecrawlFetcher(api_base=f"{fixture_server}/firecrawl"),
        ],
    )
    return Dispatcher(fetchers)


def test_dispatcher_escalates_challenge_page_to_firecrawl(
    fixture_server: str, tmp_path: Path
) -> None:
    """Real challenge-page fixture → Tier 1/2 fail → Tier 3 succeeds via mock."""
    d = _dispatcher_against_mock(fixture_server)
    env = d.run(
        f"{fixture_server}/challenge/cloudflare",
        DispatchOptions(
            auto_escalate=True,
            fetch_opts=FetchOptions(
                allow_paid=True,
                firecrawl_api_key="fc-test",
            ),
        ),
    )
    assert env.meta.tier_used == "firecrawl"
    reasons = [a.reason for a in env.meta.tier_history[:-1]]
    assert any(r.startswith("challenge:") for r in reasons)


def test_dispatcher_no_paid_means_no_firecrawl_attempt(
    fixture_server: str,
) -> None:
    from webscraper.errors import AllTiersFailedError

    d = _dispatcher_against_mock(fixture_server)
    with pytest.raises(AllTiersFailedError):
        d.run(
            f"{fixture_server}/challenge/cloudflare",
            DispatchOptions(
                auto_escalate=True,
                fetch_opts=FetchOptions(
                    allow_paid=False,
                    firecrawl_api_key="fc-test",
                ),
            ),
        )


def test_dispatcher_forced_firecrawl_skips_tier1_tier2(
    fixture_server: str,
) -> None:
    d = _dispatcher_against_mock(fixture_server)
    env = d.run(
        f"{fixture_server}/static/article",  # normally Tier 1 would succeed
        DispatchOptions(
            auto_escalate=False,
            forced_tier="firecrawl",
            fetch_opts=FetchOptions(
                allow_paid=True,
                firecrawl_api_key="fc-test",
            ),
        ),
    )
    # Firecrawl mock returns "Firecrawl: <url>" in the body
    assert env.meta.tier_used == "firecrawl"
    assert "Firecrawl:" in env.markdown or "Firecrawl:" in env.text
