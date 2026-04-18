"""Parse subpackage — aggregates all HTML extractors into FetchResult."""

from datetime import UTC, datetime

from webscraper.envelope import FetchResult, Meta, TierAttempt
from webscraper.fetch.base import FetcherResult
from webscraper.parse.body import parse_body
from webscraper.parse.forms import extract_forms
from webscraper.parse.images import extract_images
from webscraper.parse.links import extract_links
from webscraper.parse.tables import extract_tables


def parse_to_envelope(
    fr: FetcherResult,
    *,
    requested_url: str,
    tier_history: list[TierAttempt],
    now: datetime | None = None,
) -> FetchResult:
    """Turn a raw fetcher result + tier history into a canonical envelope."""
    markdown, text, title = parse_body(fr.html, requested_url=requested_url)
    tables = extract_tables(fr.html)
    forms = extract_forms(fr.html)
    images = extract_images(fr.html, base_url=fr.final_url)
    links = extract_links(fr.html, base_url=fr.final_url)
    tier_used = tier_history[-1].tier
    meta = Meta(
        tier_used=tier_used,
        tier_history=tier_history,
        http_status=fr.http_status,
        content_type=fr.content_type,
        auth_used=fr.extra.get("auth_domain", ""),
    )
    return FetchResult(
        url=requested_url,
        final_url=fr.final_url,
        fetched_at=(now or datetime.now(tz=UTC)),
        meta=meta,
        title=title,
        markdown=markdown,
        text=text,
        tables=tables,
        forms=forms,
        images=images,
        links=links,
    )
