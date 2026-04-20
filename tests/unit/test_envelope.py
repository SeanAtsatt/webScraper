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


# [F-NONE]
def test_fetch_result_roundtrips_to_json() -> None:
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


# [F-NONE]
def test_fetch_result_rejects_empty_tier_history() -> None:
    with pytest.raises(ValidationError):
        Meta(
            tier_used="fast",
            tier_history=[],
            http_status=200,
            content_type="text/html",
        )


# [F-NONE]
def test_fetch_result_tier_used_matches_last_history_entry() -> None:
    with pytest.raises(ValidationError):
        Meta(
            tier_used="browser",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        )


# [F-NONE]
def test_fetched_at_serializes_with_z_suffix() -> None:
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


# [F-NONE]
def test_image_role_accepts_enum_values_only() -> None:
    with pytest.raises(ValidationError):
        ImageSpec.model_validate(
            {"url": "https://x/y.jpg", "alt": "", "width": 0, "height": 0, "role": "sidebar"}
        )


# [F-NONE]
def test_link_kind_accepts_enum_values_only() -> None:
    with pytest.raises(ValidationError):
        LinkSpec.model_validate({"href": "/a", "text": "", "rel": "", "kind": "bogus"})


# [F-NONE]
def test_defaults_to_empty_collections() -> None:
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


# [F-NONE]
def test_meta_accepts_multi_entry_escalation_history() -> None:
    meta = Meta(
        tier_used="browser",
        tier_history=[
            TierAttempt(
                tier="fast", outcome="escalated", elapsed_ms=50, reason="insufficient_content"
            ),
            TierAttempt(tier="browser", outcome="success", elapsed_ms=800),
        ],
        http_status=200,
        content_type="text/html",
    )
    assert meta.tier_used == "browser"
    assert [a.tier for a in meta.tier_history] == ["fast", "browser"]


# [F-NONE]
def test_meta_auth_used_defaults_to_empty_string() -> None:
    meta = Meta(
        tier_used="fast",
        tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
        http_status=200,
        content_type="text/html",
    )
    assert meta.auth_used == ""


# [F-NONE]
def test_meta_auth_used_accepts_domain_string() -> None:
    meta = Meta(
        tier_used="browser",
        tier_history=[TierAttempt(tier="browser", outcome="success", elapsed_ms=1)],
        http_status=200,
        content_type="text/html",
        auth_used="connectance.org",
    )
    assert meta.auth_used == "connectance.org"


# [F-NONE]
def test_image_spec_local_path_defaults_to_empty() -> None:
    img = ImageSpec(url="https://ex.com/a.jpg")
    assert img.local_path == ""


# [F-NONE]
def test_image_spec_error_defaults_to_empty() -> None:
    img = ImageSpec(url="https://ex.com/a.jpg")
    assert img.error == ""


# [F-NONE]
def test_image_spec_accepts_local_path_and_error() -> None:
    img = ImageSpec(
        url="https://ex.com/a.jpg",
        local_path="images/abc123-a.jpg",
        error="",
    )
    assert img.local_path == "images/abc123-a.jpg"

    err_img = ImageSpec(url="https://ex.com/b.jpg", error="http_404")
    assert err_img.error == "http_404"
