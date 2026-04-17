"""Dispatcher escalation tests using mocked Fetchers."""

from dataclasses import dataclass

import pytest

from webscraper.errors import AllTiersFailedError, FetcherError
from webscraper.fetch.base import FetcherResult, FetchOptions
from webscraper.fetch.base import TierName as FetchTierName
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions

_OK_LONG = (
    "<html><head><title>ok</title></head><body>" + ("<p>lorem ipsum " * 80) + "</p></body></html>"
)
_EMPTY = "<html><body></body></html>"


@dataclass
class _MockFetcher:
    name: FetchTierName
    result: FetcherResult | None = None
    exc: Exception | None = None

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


def _fr(html: str, status: int = 200) -> FetcherResult:
    return FetcherResult(
        html=html,
        final_url="https://ex/y",
        http_status=status,
        content_type="text/html",
        elapsed_ms=10,
    )


# [F-NONE]
def test_auto_escalates_when_first_tier_returns_empty() -> None:
    d = Dispatcher(
        [_MockFetcher("fast", result=_fr(_EMPTY)), _MockFetcher("browser", result=_fr(_OK_LONG))]
    )
    env = d.run("https://ex/y", DispatchOptions(auto_escalate=True))
    assert env.meta.tier_used == "browser"
    assert [t.tier for t in env.meta.tier_history] == ["fast", "browser"]
    assert env.meta.tier_history[0].outcome == "escalated"
    assert env.meta.tier_history[1].outcome == "success"


# [F-NONE]
def test_auto_escalates_on_fetcher_exception() -> None:
    d = Dispatcher(
        [
            _MockFetcher("fast", exc=FetcherError("boom", reason="http_error")),
            _MockFetcher("browser", result=_fr(_OK_LONG)),
        ]
    )
    env = d.run("https://ex/y", DispatchOptions(auto_escalate=True))
    assert env.meta.tier_used == "browser"


# [F-NONE]
def test_explicit_tier_disables_escalation() -> None:
    d = Dispatcher(
        [_MockFetcher("fast", result=_fr(_EMPTY)), _MockFetcher("browser", result=_fr(_OK_LONG))]
    )
    with pytest.raises(AllTiersFailedError):
        d.run("https://ex/y", DispatchOptions(auto_escalate=False, forced_tier="fast"))


# [F-NONE]
def test_challenge_page_marks_tier_unacceptable() -> None:
    challenge = (
        '<html><body><div class="cf-browser-verification">'
        "Checking your browser...Cloudflare</div></body></html>"
    )
    d = Dispatcher(
        [
            _MockFetcher("fast", result=_fr(challenge)),
            _MockFetcher("browser", result=_fr(_OK_LONG)),
        ]
    )
    env = d.run("https://ex/y", DispatchOptions(auto_escalate=True))
    assert env.meta.tier_history[0].reason.startswith("challenge:")
    assert env.meta.tier_used == "browser"


# [F-NONE]
def test_all_tiers_failing_raises() -> None:
    d = Dispatcher(
        [_MockFetcher("fast", result=_fr(_EMPTY)), _MockFetcher("browser", result=_fr(_EMPTY))]
    )
    with pytest.raises(AllTiersFailedError):
        d.run("https://ex/y", DispatchOptions(auto_escalate=True))
