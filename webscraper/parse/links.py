"""Extract <a> links with kind classification."""

from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser, Node

from webscraper.envelope import LinkKind, LinkSpec

_NAV_CONTAINERS = ("nav", "header", "footer")


def _is_in_nav(el: Node) -> bool:
    parent = el.parent
    while parent is not None:
        tag = (parent.tag or "").lower()
        if tag in _NAV_CONTAINERS:
            return True
        parent = parent.parent
    return False


def _classify(href: str, base_url: str, in_nav: bool) -> tuple[str, LinkKind]:
    # Pure fragment → anchor
    if href.startswith("#"):
        return urljoin(base_url, href), "anchor"
    resolved = urljoin(base_url, href)
    base_host = urlparse(base_url).netloc
    target_host = urlparse(resolved).netloc
    if target_host and target_host != base_host:
        return resolved, "external"
    if in_nav:
        return resolved, "nav"
    return resolved, "content"


def extract_links(html: str, *, base_url: str) -> list[LinkSpec]:
    tree = HTMLParser(html)
    out: list[LinkSpec] = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href") or ""
        if not href:
            continue
        resolved, kind = _classify(href, base_url, _is_in_nav(a))
        out.append(
            LinkSpec(
                href=resolved,
                text=a.text(strip=True),
                rel=a.attributes.get("rel") or "",
                kind=kind,
            )
        )
    return out
