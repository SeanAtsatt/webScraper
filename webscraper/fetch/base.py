"""Shared types for all Fetcher implementations."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

TierName = Literal["fast", "browser", "firecrawl"]


@dataclass(frozen=True)
class FetchOptions:
    timeout_s: float = 30.0
    max_body_bytes: int = 50 * 1024 * 1024
    user_agent: str = "webscraper/0.1 (+https://example.invalid)"
    chrome_profile_path: str | None = None


@dataclass
class FetcherResult:
    html: str
    final_url: str
    http_status: int
    content_type: str
    elapsed_ms: int
    extra: dict[str, str] = field(default_factory=dict)


class Fetcher(Protocol):
    name: TierName

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult: ...
