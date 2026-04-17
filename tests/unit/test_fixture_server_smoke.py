"""Smoke test that the fixture server boots and serves a page."""

import httpx


# [F-NONE]
def test_fixture_server_serves_static(fixture_server: str) -> None:
    resp = httpx.get(f"{fixture_server}/static/article", timeout=5)
    assert resp.status_code == 200
    assert "Static Article" in resp.text
