"""Challenge-page fingerprinting (Cloudflare IUAM, PerimeterX, Akamai)."""

import re

_FINGERPRINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "cloudflare",
        re.compile(r"cf-browser-verification|Checking your browser.+Cloudflare", re.I | re.S),
    ),
    ("perimeterx", re.compile(r"PerimeterX|verify you are a human", re.I)),
    (
        "akamai",
        re.compile(r"Reference #\d+\.[a-f0-9]+\.\d+\.\w+|Access Denied.*Akamai", re.I | re.S),
    ),
)


def is_challenge_page(html: str) -> tuple[bool, str]:
    for name, pattern in _FINGERPRINTS:
        if pattern.search(html):
            return True, f"challenge:{name}"
    return False, ""
