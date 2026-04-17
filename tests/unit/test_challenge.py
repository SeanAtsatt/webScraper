"""Anti-bot challenge-page detection."""

from webscraper.challenge import is_challenge_page


# [F-NONE]
def test_detects_cloudflare_iuam() -> None:
    html = '<div class="cf-browser-verification">Checking your browser...Cloudflare</div>'
    detected, reason = is_challenge_page(html)
    assert detected is True
    assert "cloudflare" in reason.lower()


# [F-NONE]
def test_detects_perimeterx_by_phrase() -> None:
    html = "<html><body>Please verify you are a human. PerimeterX</body></html>"
    detected, reason = is_challenge_page(html)
    assert detected is True
    assert "perimeterx" in reason.lower()


# [F-NONE]
def test_detects_akamai_block_page() -> None:
    html = "<p>Access denied — Reference #18.abc.1234567890.12345</p>"
    detected, reason = is_challenge_page(html)
    assert detected is True
    assert "akamai" in reason.lower()


# [F-NONE]
def test_passes_normal_content() -> None:
    html = "<html><body><h1>Article</h1><p>Lots of real content here.</p></body></html>"
    detected, _ = is_challenge_page(html)
    assert detected is False
