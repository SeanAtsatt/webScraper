"""RobotsChecker tests."""

from webscraper.crawl.robots import RobotsChecker


# [F-REQ-028]
def test_robots_allows_unrestricted_path(fixture_server: str) -> None:
    r = RobotsChecker(fixture_server, user_agent="webscraper/0.2", timeout_s=5.0)
    assert r.allowed(f"{fixture_server}/crawl/a")


# [F-REQ-028]
def test_robots_disallows_admin_path(fixture_server: str) -> None:
    r = RobotsChecker(fixture_server, user_agent="webscraper/0.2", timeout_s=5.0)
    assert not r.allowed(f"{fixture_server}/crawl/admin/secret")


# [F-REQ-028]
def test_robots_defaults_to_allowed_when_fetch_fails() -> None:
    # Use a host that won't respond; the checker should allow by default.
    r = RobotsChecker("http://127.0.0.1:1", user_agent="webscraper/0.2", timeout_s=1.0)
    assert r.allowed("http://127.0.0.1:1/anything")
