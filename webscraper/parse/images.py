"""Extract <img> and CSS background-image URLs with role classification."""

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

from webscraper.envelope import ImageRole, ImageSpec

_BG_URL = re.compile(r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)", re.IGNORECASE)
_HERO_MIN_WIDTH = 900
_ICON_MAX_DIM = 48


def _role(width: int, height: int, *, is_background: bool) -> ImageRole:
    if is_background:
        return "background"
    if width >= _HERO_MIN_WIDTH:
        return "hero"
    if 0 < width <= _ICON_MAX_DIM and 0 < height <= _ICON_MAX_DIM:
        return "icon"
    return "inline"


def _int_attr(el: Node, name: str) -> int:
    v = el.attributes.get(name) or ""
    try:
        return int(v)
    except ValueError:
        return 0


def extract_images(html: str, *, base_url: str) -> list[ImageSpec]:
    tree = HTMLParser(html)
    out: list[ImageSpec] = []
    for img in tree.css("img"):
        src = img.attributes.get("src") or ""
        if not src:
            continue
        url = urljoin(base_url, src)
        width = _int_attr(img, "width")
        height = _int_attr(img, "height")
        out.append(
            ImageSpec(
                url=url,
                alt=img.attributes.get("alt") or "",
                width=width,
                height=height,
                role=_role(width, height, is_background=False),
            )
        )

    for style_el in tree.css("style"):
        css_text = style_el.text() or ""
        for match in _BG_URL.finditer(css_text):
            out.append(
                ImageSpec(
                    url=urljoin(base_url, match.group(1)),
                    role=_role(0, 0, is_background=True),
                )
            )
    for el in tree.css("[style]"):
        style = el.attributes.get("style") or ""
        for match in _BG_URL.finditer(style):
            out.append(
                ImageSpec(
                    url=urljoin(base_url, match.group(1)),
                    role=_role(0, 0, is_background=True),
                )
            )
    return out
