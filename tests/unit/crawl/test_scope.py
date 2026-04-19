"""Scope check + path glob filter tests."""

from webscraper.crawl.scope import is_same_site, matches_path_globs


# [F-REQ-026]
def test_same_site_across_subdomains() -> None:
    assert is_same_site("https://www.ex.com/", "https://app.ex.com/")
    assert is_same_site("https://ex.com/", "https://foo.bar.ex.com/")


# [F-REQ-026]
def test_same_site_rejects_different_registrable_domain() -> None:
    assert not is_same_site("https://ex.com/", "https://other.com/")
    assert not is_same_site("https://ex.com/", "https://evil-ex.com/")


# [F-REQ-026]
def test_same_site_handles_multilevel_tld() -> None:
    assert is_same_site("https://ex.co.uk/", "https://www.ex.co.uk/")
    assert not is_same_site("https://ex.co.uk/", "https://other.co.uk/")


# [F-REQ-027]
def test_path_globs_empty_includes_accepts_everything() -> None:
    assert matches_path_globs("https://ex.com/a/b", (), ())


# [F-REQ-027]
def test_path_globs_exclude_matches() -> None:
    assert not matches_path_globs("https://ex.com/admin/x", (), ("/admin/**",))


# [F-REQ-027]
def test_path_globs_include_requires_match() -> None:
    assert matches_path_globs("https://ex.com/docs/a", ("/docs/**",), ())
    assert not matches_path_globs("https://ex.com/blog/a", ("/docs/**",), ())


# [F-REQ-027]
def test_path_globs_exclude_wins_over_include() -> None:
    assert not matches_path_globs(
        "https://ex.com/docs/old/a",
        includes=("/docs/**",),
        excludes=("/docs/old/**",),
    )
