"""Smoke test for the fixture server's mock Firecrawl endpoint."""

import httpx


# [F-NONE]
def test_firecrawl_mock_requires_bearer(fixture_server: str) -> None:
    resp = httpx.post(
        f"{fixture_server}/firecrawl/v1/scrape",
        json={"url": "https://ex.com/"},
        timeout=5,
    )
    assert resp.status_code == 401


# [F-NONE]
def test_firecrawl_mock_returns_canned_scrape(fixture_server: str) -> None:
    resp = httpx.post(
        f"{fixture_server}/firecrawl/v1/scrape",
        json={"url": "https://ex.com/"},
        headers={"Authorization": "Bearer fc-test"},
        timeout=5,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "Firecrawl:" in body["data"]["html"]


# [F-NONE]
def test_firecrawl_mock_honors_force_402(fixture_server: str) -> None:
    resp = httpx.post(
        f"{fixture_server}/firecrawl/v1/scrape",
        json={"url": "https://ex.com/force-402"},
        headers={"Authorization": "Bearer fc-test"},
        timeout=5,
    )
    assert resp.status_code == 402
