"""Envelope schema tests."""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from webscraper.envelope import (
    FetchResult,
    ImageSpec,
    LinkSpec,
    Meta,
    TierAttempt,
)


def test_fetch_result_roundtrips_to_json():
    result = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=120)],
            http_status=200,
            content_type="text/html; charset=utf-8",
        ),
        title="Example",
        markdown="# Example",
        text="Example",
        tables=[],
        forms=[],
        images=[],
        links=[],
    )
    json_blob = result.model_dump_json()
    reparsed = FetchResult.model_validate_json(json_blob)
    assert reparsed == result


def test_fetch_result_rejects_empty_tier_history():
    with pytest.raises(ValidationError):
        Meta(
            tier_used="fast",
            tier_history=[],
            http_status=200,
            content_type="text/html",
        )


def test_fetch_result_tier_used_matches_last_history_entry():
    with pytest.raises(ValidationError):
        Meta(
            tier_used="browser",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        )


def test_fetched_at_serializes_with_z_suffix():
    result = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        ),
        title="",
        markdown="",
        text="",
    )
    assert '"fetched_at":"2026-04-16T12:00:00Z"' in result.model_dump_json()


def test_image_role_accepts_enum_values_only():
    with pytest.raises(ValidationError):
        ImageSpec(url="https://x/y.jpg", alt="", width=0, height=0, role="sidebar")


def test_link_kind_accepts_enum_values_only():
    with pytest.raises(ValidationError):
        LinkSpec(href="/a", text="", rel="", kind="bogus")


def test_defaults_to_empty_collections():
    result = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=UTC),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        ),
        title="",
        markdown="",
        text="",
    )
    assert result.tables == []
    assert result.forms == []
    assert result.images == []
    assert result.links == []
