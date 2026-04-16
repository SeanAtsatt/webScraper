"""Typed error hierarchy for webscraper."""


class WebscraperError(Exception):
    """Base error; subclasses add semantic meaning."""


class UsageError(WebscraperError):
    """Bad CLI arguments or malformed URL."""


class EnvironmentError(WebscraperError):  # noqa: A001 — intentional shadow
    """Playwright or Chrome profile missing."""


class FetcherError(WebscraperError):
    """Generic fetch failure; subclasses specialize."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class TimeoutError(FetcherError):  # noqa: A001
    """Fetch exceeded the configured timeout."""


class RedirectLoopError(FetcherError):
    """Fetch entered a redirect loop."""


class TooLargeError(FetcherError):
    """Response body exceeded the hard cap."""


class AllTiersFailedError(WebscraperError):
    """All attempted tiers returned unacceptable results."""
