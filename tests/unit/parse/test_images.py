"""Image extraction and role classification tests."""

from webscraper.parse.images import extract_images


# [F-NONE]
def test_classifies_hero_inline_icon_and_background() -> None:
    html = """
    <html><head>
    <style>.bg { background-image: url('/img/bg.jpg'); }</style>
    </head><body>
      <img src="/img/hero.jpg" alt="Hero" width="1200" height="630" />
      <img src="/img/inline.png" alt="Inline" width="400" height="300" />
      <img src="/img/icon.png" alt="" width="16" height="16" />
      <div class="bg"></div>
    </body></html>
    """
    images = extract_images(html, base_url="https://ex.com/")
    roles = {img.url: img.role for img in images}
    assert roles["https://ex.com/img/hero.jpg"] == "hero"
    assert roles["https://ex.com/img/inline.png"] == "inline"
    assert roles["https://ex.com/img/icon.png"] == "icon"
    assert roles["https://ex.com/img/bg.jpg"] == "background"


# [F-NONE]
def test_empty_when_no_images() -> None:
    assert extract_images("<p>nothing</p>", base_url="https://x/") == []


# [F-NONE]
def test_resolves_relative_urls_against_base() -> None:
    html = '<img src="foo.png" alt="" />'
    images = extract_images(html, base_url="https://ex.com/a/b/")
    assert images[0].url == "https://ex.com/a/b/foo.png"
