"""Smoke test that the crawl fixture routes serve expected content."""

import httpx


def test_crawl_index_serves_prose(fixture_server: str) -> None:
    resp = httpx.get(f"{fixture_server}/crawl/", timeout=5)
    assert resp.status_code == 200
    assert "Crawl Index" in resp.text


def test_robots_txt_disallows_admin(fixture_server: str) -> None:
    resp = httpx.get(f"{fixture_server}/robots.txt", timeout=5)
    assert resp.status_code == 200
    assert "Disallow: /crawl/admin/" in resp.text
