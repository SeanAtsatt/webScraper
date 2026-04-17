"""Link extraction and kind classification tests."""

from webscraper.parse.links import extract_links


# [F-NONE]
def test_classifies_nav_content_external_anchor() -> None:
    html = """
    <html><body>
      <nav><a href="/about">About</a><a href="/">Home</a></nav>
      <article><p><a href="/articles/2026/p1">Read more</a></p></article>
      <a href="https://external.example/">external</a>
      <a href="#s2">jump</a>
    </body></html>
    """
    links = extract_links(html, base_url="https://ex.com/current")
    kinds = {link.href: link.kind for link in links}
    assert kinds["https://ex.com/about"] == "nav"
    assert kinds["https://ex.com/"] == "nav"
    assert kinds["https://ex.com/articles/2026/p1"] == "content"
    assert kinds["https://external.example/"] == "external"
    assert kinds["https://ex.com/current#s2"] == "anchor"


# [F-NONE]
def test_empty_when_no_links() -> None:
    assert extract_links("<p>none</p>", base_url="https://ex.com/") == []
