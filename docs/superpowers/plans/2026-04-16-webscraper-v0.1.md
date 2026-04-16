# webScraper v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `webscraper` v0.1 — a Python CLI that fetches any URL and returns a canonical JSON envelope, with automatic escalation between an `httpx` fast-tier and a Playwright browser-tier, Chrome-profile-based auth, and a complete E2E test suite tied to `[F-REQ-xxx]` entries.

**Architecture:** Monolithic CLI (Option A from `docs/ARCH.md`). One Python process. Backends behind a `Fetcher` Protocol. Dispatcher enforces the escalation rule. `HtmlParser` produces a single Pydantic `FetchResult` envelope. Renderers are post-processors. Tests run offline against a local FastAPI fixture server.

**Tech Stack:** Python 3.11+, `uv` for deps, `httpx` (Tier 1), `trafilatura` + `readability-lxml` + `selectolax` + `markdownify` (parsing), `playwright` (Tier 2), `pydantic` (envelope), `FastAPI` + `uvicorn` (fixture server), `pytest` + `pytest-asyncio` + `pytest-playwright` (tests), `ruff` + `mypy` (quality).

**Reference docs:** `docs/PRD.md` (requirements, envelope schema, 15 F-REQs), `docs/ARCH.md` (component boundaries, data flows, failure modes), `README.md` (user-facing contract), `FUNCTIONAL-REQUIREMENTS.md` (requirement registry).

---

## File Structure

```
pyproject.toml                          # deps, ruff, mypy, pytest config
uv.lock                                 # (generated)

webscraper/
  __init__.py                           # __version__
  __main__.py                           # `python -m webscraper` entry
  cli.py                                # argparse dispatch, exit codes
  errors.py                             # typed error hierarchy
  log.py                                # structured JSON logger + redaction filter
  envelope.py                           # Pydantic FetchResult
  challenge.py                          # anti-bot page fingerprints
  profile.py                            # Chrome profile locate + copy-on-run
  doctor.py                             # `webscraper doctor` checks

  fetch/
    __init__.py
    base.py                             # Fetcher Protocol, FetcherResult, FetcherError
    fast.py                             # FastFetcher (httpx)
    browser.py                          # BrowserFetcher (Playwright)
    dispatcher.py                       # tier selection + escalation

  parse/
    __init__.py                         # HtmlParser.parse entrypoint
    body.py                             # trafilatura → readability fallback → markdown
    tables.py                           # <table> → {headers, rows}
    forms.py                            # <form> → {action, method, fields}
    images.py                           # <img>, background-image → images with role
    links.py                            # <a> → links with kind classification

  render/
    __init__.py
    markdown.py                         # envelope → markdown
    html.py                             # envelope → self-contained HTML preview

tests/
  __init__.py
  conftest.py                           # shared fixtures (fixture server, tmp Chrome profile)
  fixtures/
    __init__.py
    server.py                           # FastAPI fixture server
    pages/
      static.html
      spa.html
      auth_private.html
      challenge_cloudflare.html
      tables.html
      forms.html
      images.html
      links.html
  unit/
    test_envelope.py
    test_log.py
    test_challenge.py
    test_profile.py
    fetch/
      test_dispatcher.py
    parse/
      test_body.py
      test_tables.py
      test_forms.py
      test_images.py
      test_links.py
    render/
      test_markdown.py
      test_html.py
  integration/
    test_fast_fetcher.py
    test_browser_fetcher.py
    test_cli_fetch.py
    test_cli_doctor.py
  e2e/
    test_fetch_flows.py                 # [F-REQ-xxx]-tagged tests

docs/ADR/
  ADR-001-tiered-fetcher.md             # record the Option A choice
FUNCTIONAL-REQUIREMENTS.md              # append 15 F-REQ rows
```

Responsibilities are kept tight: one parser per structural feature, one fetcher per tier, one rendering target per file. Files that change together live together (parsers in `parse/`, fetchers in `fetch/`, renderers in `render/`).

---

## Task 1: Bootstrap Python project

**Files:**
- Create: `pyproject.toml`
- Create: `webscraper/__init__.py`
- Create: `webscraper/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/e2e/__init__.py`
- Create: `tests/fixtures/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "webscraper"
version = "0.1.0"
description = "AI-driven web scraper with tiered fetch backends"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "trafilatura>=1.12",
    "readability-lxml>=0.8.1",
    "selectolax>=0.3.21",
    "markdownify>=0.13",
    "playwright>=1.47",
    "pydantic>=2.7",
    "fastapi>=0.115",
    "uvicorn>=0.30",
]

[project.scripts]
webscraper = "webscraper.cli:main"

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-playwright>=0.5",
    "httpx[cli]>=0.27",
    "ruff>=0.6",
    "mypy>=1.11",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "C4", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `webscraper/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `webscraper/__main__.py`**

```python
from webscraper.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create test package init files**

Each of these should contain a single-line docstring and nothing else:

```python
"""<purpose>."""
```

Paths: `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/e2e/__init__.py`, `tests/fixtures/__init__.py`.

- [ ] **Step 5: Create a stub `webscraper/cli.py` so `uv sync` resolves the entrypoint**

```python
def main() -> int:
    """Stub CLI entry — real implementation arrives in Task 20."""
    return 0
```

- [ ] **Step 6: Resolve deps**

Run: `uv sync`
Expected: `.venv/` created, `uv.lock` generated. Exit 0.

- [ ] **Step 7: Install Playwright browser**

Run: `uv run playwright install chromium`
Expected: Chromium installed to `~/.cache/ms-playwright/` (platform-dependent). Exit 0.

- [ ] **Step 8: Verify quality tools run clean on the skeleton**

Run: `uv run ruff check . && uv run mypy . && uv run pytest`
Expected: ruff passes, mypy passes, pytest collects 0 tests and exits 5 (no tests). We'll treat exit 5 as OK at this stage; subsequent tasks add tests.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock webscraper tests
git commit -m "feat: bootstrap webscraper Python package"
```

---

## Task 2: Envelope schema (`FetchResult` Pydantic model)

**Files:**
- Create: `webscraper/envelope.py`
- Test: `tests/unit/test_envelope.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_envelope.py
"""Envelope schema tests."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from webscraper.envelope import (
    FetchResult,
    FormField,
    FormSpec,
    ImageSpec,
    LinkSpec,
    Meta,
    TableSpec,
    TierAttempt,
)


def test_fetch_result_roundtrips_to_json():
    result = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=120)],
            http_status=200,
            content_type="text/html; charset=utf-8",
        ),
        title="Example",
        markdown="# Example",
        text="Example",
        tables=[],
        forms=[],
        images=[],
        links=[],
    )
    json_blob = result.model_dump_json()
    reparsed = FetchResult.model_validate_json(json_blob)
    assert reparsed == result


def test_fetch_result_rejects_empty_tier_history():
    with pytest.raises(ValidationError):
        Meta(
            tier_used="fast",
            tier_history=[],
            http_status=200,
            content_type="text/html",
        )


def test_fetch_result_tier_used_matches_last_history_entry():
    with pytest.raises(ValidationError):
        Meta(
            tier_used="browser",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        )


def test_fetched_at_serializes_with_z_suffix():
    result = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        ),
        title="",
        markdown="",
        text="",
    )
    assert '"fetched_at":"2026-04-16T12:00:00Z"' in result.model_dump_json()


def test_image_role_accepts_enum_values_only():
    with pytest.raises(ValidationError):
        ImageSpec(url="https://x/y.jpg", alt="", width=0, height=0, role="sidebar")


def test_link_kind_accepts_enum_values_only():
    with pytest.raises(ValidationError):
        LinkSpec(href="/a", text="", rel="", kind="bogus")


def test_defaults_to_empty_collections():
    result = FetchResult(
        url="https://example.com",
        final_url="https://example.com",
        fetched_at=datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200,
            content_type="text/html",
        ),
        title="",
        markdown="",
        text="",
    )
    assert result.tables == []
    assert result.forms == []
    assert result.images == []
    assert result.links == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_envelope.py -v`
Expected: 7 FAIL (module not importable).

- [ ] **Step 3: Implement `webscraper/envelope.py`**

```python
"""Canonical envelope schema for webscraper fetch results."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

TierName = Literal["fast", "browser", "firecrawl"]
TierOutcome = Literal["success", "escalated", "failed"]
ImageRole = Literal["hero", "inline", "icon", "background"]
LinkKind = Literal["nav", "content", "external", "anchor"]


class TierAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: TierName
    outcome: TierOutcome
    elapsed_ms: int = Field(ge=0)
    reason: str = ""


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier_used: TierName
    tier_history: list[TierAttempt] = Field(min_length=1)
    http_status: int
    content_type: str

    @model_validator(mode="after")
    def _tier_used_matches_last_history(self) -> "Meta":
        if self.tier_history[-1].tier != self.tier_used:
            raise ValueError("tier_used must equal tier_history[-1].tier")
        return self


class TableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headers: list[str] = []
    rows: list[list[str]] = []


class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    label: str = ""


class FormSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = ""
    method: str = "GET"
    fields: list[FormField] = []


class ImageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    alt: str = ""
    width: int = 0
    height: int = 0
    role: ImageRole = "inline"


class LinkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    href: str
    text: str = ""
    rel: str = ""
    kind: LinkKind = "content"


class FetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    final_url: str
    fetched_at: datetime
    meta: Meta
    title: str
    markdown: str
    text: str
    tables: list[TableSpec] = []
    forms: list[FormSpec] = []
    images: list[ImageSpec] = []
    links: list[LinkSpec] = []

    @field_serializer("fetched_at")
    def _serialize_fetched_at(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_envelope.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/envelope.py tests/unit/test_envelope.py
git commit -m "feat(envelope): Pydantic schema for FetchResult"
```

---

## Task 3: Typed errors

**Files:**
- Create: `webscraper/errors.py`

- [ ] **Step 1: Implement**

```python
"""Typed error hierarchy for webscraper."""


class WebscraperError(Exception):
    """Base error; subclasses add semantic meaning."""


class UsageError(WebscraperError):
    """Bad CLI arguments or malformed URL."""


class EnvironmentError(WebscraperError):  # noqa: A001 — intentional shadow
    """Playwright or Chrome profile missing."""


class FetcherError(WebscraperError):
    """Generic fetch failure; subclasses specialize."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class TimeoutError(FetcherError):  # noqa: A001
    """Fetch exceeded the configured timeout."""


class RedirectLoopError(FetcherError):
    """Fetch entered a redirect loop."""


class TooLargeError(FetcherError):
    """Response body exceeded the hard cap."""


class AllTiersFailedError(WebscraperError):
    """All attempted tiers returned unacceptable results."""
```

- [ ] **Step 2: Commit** (no tests — this is pure type declaration; errors are exercised in consumer tests)

```bash
git add webscraper/errors.py
git commit -m "feat(errors): typed error hierarchy"
```

---

## Task 4: Structured logger with redaction filter

**Files:**
- Create: `webscraper/log.py`
- Test: `tests/unit/test_log.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_log.py
"""Structured logger and redaction filter tests."""
import json
import logging

from webscraper.log import RedactionFilter, configure, get_logger


def test_logger_emits_jsonl(capsys):
    configure(level="INFO")
    log = get_logger("t")
    log.info("hello", extra={"extra_k": "v"})
    captured = capsys.readouterr().err.strip().splitlines()
    record = json.loads(captured[-1])
    assert record["level"] == "INFO"
    assert record["event"] == "hello"
    assert record["extra_k"] == "v"
    assert "ts" in record


def test_redaction_filter_strips_cookie_header():
    f = RedactionFilter()
    record = logging.makeLogRecord({
        "msg": "req",
        "args": (),
        "Cookie": "session=secret",
        "headers": {"Cookie": "session=secret", "User-Agent": "ua"},
    })
    assert f.filter(record) is True
    assert record.__dict__["Cookie"] == "[REDACTED]"
    assert record.__dict__["headers"]["Cookie"] == "[REDACTED]"
    assert record.__dict__["headers"]["User-Agent"] == "ua"


def test_redaction_covers_authorization_and_auth_prefix():
    f = RedactionFilter()
    record = logging.makeLogRecord({
        "msg": "req",
        "args": (),
        "Authorization": "Bearer abc",
        "X-Auth-Token": "xyz",
    })
    f.filter(record)
    assert record.__dict__["Authorization"] == "[REDACTED]"
    assert record.__dict__["X-Auth-Token"] == "[REDACTED]"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_log.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Implement `webscraper/log.py`**

```python
"""Structured JSON-line logger with cookie/credential redaction."""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = ("cookie", "set-cookie", "authorization")
_SENSITIVE_PREFIX = ("x-auth-",)


class RedactionFilter(logging.Filter):
    """Strip cookie-like and auth-like values from log records (top-level and nested dicts)."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in list(record.__dict__.keys()):
            record.__dict__[key] = self._scrub(key, record.__dict__[key])
        return True

    def _scrub(self, key: str, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._scrub(k, v) for k, v in value.items()}
        if self._is_sensitive(key):
            return REDACTED
        return value

    @staticmethod
    def _is_sensitive(key: str) -> bool:
        k = key.lower()
        if k in _SENSITIVE_KEYS:
            return True
        return any(k.startswith(p) for p in _SENSITIVE_PREFIX)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        standard = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
        }
        for k, v in record.__dict__.items():
            if k in standard:
                continue
            payload[k] = v
        return json.dumps(payload, default=str)


def configure(*, level: str = "INFO", stream: Any = None) -> None:
    """Install the JSON formatter and redaction filter on the root logger."""
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"webscraper.{name}")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_log.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/log.py tests/unit/test_log.py
git commit -m "feat(log): structured JSON logger with redaction filter"
```

---

## Task 5: Fixture server

**Files:**
- Create: `tests/fixtures/server.py`
- Create: `tests/fixtures/pages/static.html`
- Create: `tests/fixtures/pages/spa.html`
- Create: `tests/fixtures/pages/auth_private.html`
- Create: `tests/fixtures/pages/challenge_cloudflare.html`
- Create: `tests/fixtures/pages/tables.html`
- Create: `tests/fixtures/pages/forms.html`
- Create: `tests/fixtures/pages/images.html`
- Create: `tests/fixtures/pages/links.html`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the fixture HTML files**

Each file is a minimal, deterministic page with the features named in its filename. Exact content (copy verbatim):

`tests/fixtures/pages/static.html`:
```html
<!doctype html>
<html><head><title>Static Article</title></head>
<body>
  <h1>Static Article</h1>
  <p>This is a static article page. It has enough content that trafilatura
  will extract a meaningful body. The lazy brown fox jumps over the fence
  while the quick dog watches from the porch, unconcerned.</p>
  <p>Second paragraph with more prose for bulk. Lorem ipsum dolor sit amet,
  consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore
  et dolore magna aliqua.</p>
</body></html>
```

`tests/fixtures/pages/spa.html`:
```html
<!doctype html>
<html><head><title>SPA Shell</title></head>
<body>
  <div id="root"></div>
  <script>
    window.addEventListener("DOMContentLoaded", () => {
      document.getElementById("root").innerHTML =
        "<h1>SPA Rendered</h1><p>This content was injected by JavaScript after load. " +
        "Tier 1 should not see this; Tier 2 should.</p>";
    });
  </script>
</body></html>
```

`tests/fixtures/pages/auth_private.html`:
```html
<!doctype html>
<html><head><title>Private Area</title></head>
<body>
  <h1>Authenticated Content</h1>
  <p>You are logged in. Here is the private content only visible with the
  fixture_auth cookie set.</p>
</body></html>
```

`tests/fixtures/pages/challenge_cloudflare.html`:
```html
<!doctype html>
<html><head><title>Just a moment...</title></head>
<body>
  <div class="cf-browser-verification">
    <h1>Checking your browser before accessing the site.</h1>
    <p>This process is automatic. Your browser will redirect shortly.</p>
    <p>Ray ID: 7abc123def456789</p>
    <p>Cloudflare</p>
  </div>
</body></html>
```

`tests/fixtures/pages/tables.html`:
```html
<!doctype html>
<html><head><title>Tables</title></head>
<body>
  <table>
    <thead><tr><th>Name</th><th>Email</th></tr></thead>
    <tbody>
      <tr><td>Alice</td><td>alice@example.com</td></tr>
      <tr><td>Bob</td><td>bob@example.com</td></tr>
    </tbody>
  </table>
  <table>
    <tr><th>A</th><th>B</th></tr>
    <tr><td>1</td><td>2</td></tr>
  </table>
</body></html>
```

`tests/fixtures/pages/forms.html`:
```html
<!doctype html>
<html><head><title>Forms</title></head>
<body>
  <form action="/submit" method="POST">
    <label for="q">Search</label>
    <input type="text" id="q" name="q" />
    <label for="opt">Option</label>
    <select id="opt" name="opt"><option>x</option></select>
    <textarea name="notes"></textarea>
    <input type="checkbox" name="agree" />
    <button type="submit">Go</button>
  </form>
</body></html>
```

`tests/fixtures/pages/images.html`:
```html
<!doctype html>
<html><head><title>Images</title>
<style>.bg { background-image: url('/img/bg.jpg'); width: 200px; height: 100px; }</style>
</head>
<body>
  <img src="/img/hero.jpg" alt="Hero" width="1200" height="630" />
  <p>Prose with inline image: <img src="/img/inline.png" alt="Inline" width="400" height="300" /></p>
  <img src="/img/icon.png" alt="" width="16" height="16" />
  <div class="bg"></div>
</body></html>
```

`tests/fixtures/pages/links.html`:
```html
<!doctype html>
<html><head><title>Links</title></head>
<body>
  <nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
  </nav>
  <article>
    <p>Read more <a href="/articles/2026/post-1">here</a> and visit
    <a href="https://external.example/">external</a>.</p>
    <p>Jump to <a href="#section-2">section 2</a>.</p>
  </article>
</body></html>
```

- [ ] **Step 2: Implement the fixture server**

```python
# tests/fixtures/server.py
"""Local FastAPI app serving deterministic pages for tests."""
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

_PAGES = Path(__file__).parent / "pages"


def read(name: str) -> str:
    return (_PAGES / name).read_text(encoding="utf-8")


def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/static/article", response_class=HTMLResponse)
    def static_article() -> str:
        return read("static.html")

    @app.get("/spa/app", response_class=HTMLResponse)
    def spa() -> str:
        return read("spa.html")

    @app.get("/auth/private")
    def auth_private(request: Request):
        if request.cookies.get("fixture_auth") != "1":
            return Response("unauthorized", status_code=401)
        return HTMLResponse(read("auth_private.html"))

    @app.get("/auth/login")
    def auth_login(response: Response) -> Response:
        resp = HTMLResponse("<p>logged in</p>")
        resp.set_cookie("fixture_auth", "1", path="/")
        return resp

    @app.get("/challenge/cloudflare", response_class=HTMLResponse)
    def challenge() -> str:
        return read("challenge_cloudflare.html")

    @app.get("/table/large", response_class=HTMLResponse)
    def tables() -> str:
        return read("tables.html")

    @app.get("/forms/login", response_class=HTMLResponse)
    def forms() -> str:
        return read("forms.html")

    @app.get("/images/mixed", response_class=HTMLResponse)
    def images() -> str:
        return read("images.html")

    @app.get("/links/mixed", response_class=HTMLResponse)
    def links() -> str:
        return read("links.html")

    @app.get("/slow")
    def slow() -> PlainTextResponse:
        import time
        time.sleep(5)
        return PlainTextResponse("slow")

    @app.get("/redirect-loop")
    def redirect_loop() -> RedirectResponse:
        return RedirectResponse("/redirect-loop")

    @app.get("/oversize")
    def oversize() -> PlainTextResponse:
        return PlainTextResponse("x" * (60 * 1024 * 1024))

    @app.get("/img/{name}")
    def image_asset(name: str) -> Response:
        return Response(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, media_type="image/png")

    return app
```

- [ ] **Step 3: Add a pytest fixture that runs the server in-process**

```python
# tests/conftest.py
"""Shared pytest fixtures."""
from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from tests.fixtures.server import create_app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def fixture_server() -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("fixture server failed to start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
```

- [ ] **Step 4: Smoke-test the fixture server**

Add this temporary test at `tests/unit/test_fixture_server_smoke.py`:
```python
"""Smoke test that the fixture server boots and serves a page."""
import httpx


def test_fixture_server_serves_static(fixture_server):
    resp = httpx.get(f"{fixture_server}/static/article", timeout=5)
    assert resp.status_code == 200
    assert "Static Article" in resp.text
```

Run: `uv run pytest tests/unit/test_fixture_server_smoke.py -v`
Expected: 1 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/conftest.py tests/unit/test_fixture_server_smoke.py
git commit -m "test(fixtures): local FastAPI fixture server with test pages"
```

---

## Task 6: `Fetcher` Protocol, `FetcherResult`, base utilities

**Files:**
- Create: `webscraper/fetch/__init__.py`
- Create: `webscraper/fetch/base.py`

- [ ] **Step 1: Implement**

```python
# webscraper/fetch/__init__.py
"""Fetch subpackage."""
from webscraper.fetch.base import FetchOptions, Fetcher, FetcherResult

__all__ = ["Fetcher", "FetcherResult", "FetchOptions"]
```

```python
# webscraper/fetch/base.py
"""Shared types for all Fetcher implementations."""
from dataclasses import dataclass, field
from typing import Literal, Protocol

TierName = Literal["fast", "browser", "firecrawl"]


@dataclass(frozen=True)
class FetchOptions:
    timeout_s: float = 30.0
    max_body_bytes: int = 50 * 1024 * 1024
    user_agent: str = "webscraper/0.1 (+https://example.invalid)"
    chrome_profile_path: str | None = None


@dataclass
class FetcherResult:
    html: str
    final_url: str
    http_status: int
    content_type: str
    elapsed_ms: int
    extra: dict[str, str] = field(default_factory=dict)


class Fetcher(Protocol):
    name: TierName

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult: ...
```

- [ ] **Step 2: Commit** (no tests — pure declarations exercised by downstream tests)

```bash
git add webscraper/fetch/__init__.py webscraper/fetch/base.py
git commit -m "feat(fetch): Fetcher Protocol and shared result types"
```

---

## Task 7: FastFetcher (Tier 1)

**Files:**
- Create: `webscraper/fetch/fast.py`
- Test: `tests/integration/test_fast_fetcher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_fast_fetcher.py
"""FastFetcher integration tests against the fixture server."""
import pytest

from webscraper.errors import RedirectLoopError, TooLargeError
from webscraper.fetch.base import FetchOptions
from webscraper.fetch.fast import FastFetcher


def test_fast_fetcher_retrieves_static_page(fixture_server):
    f = FastFetcher()
    result = f.fetch(f"{fixture_server}/static/article", FetchOptions())
    assert result.http_status == 200
    assert "Static Article" in result.html
    assert result.final_url.endswith("/static/article")
    assert result.elapsed_ms >= 0


def test_fast_fetcher_raises_on_redirect_loop(fixture_server):
    f = FastFetcher()
    with pytest.raises(RedirectLoopError):
        f.fetch(f"{fixture_server}/redirect-loop", FetchOptions())


def test_fast_fetcher_raises_on_oversize(fixture_server):
    f = FastFetcher()
    with pytest.raises(TooLargeError):
        f.fetch(f"{fixture_server}/oversize", FetchOptions(max_body_bytes=1_000_000))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/integration/test_fast_fetcher.py -v`
Expected: 3 FAIL (module not importable).

- [ ] **Step 3: Implement**

```python
# webscraper/fetch/fast.py
"""Tier 1 fetcher: httpx + retries + body cap."""
import time

import httpx

from webscraper.errors import FetcherError, RedirectLoopError, TimeoutError, TooLargeError
from webscraper.fetch.base import FetchOptions, FetcherResult


class FastFetcher:
    name = "fast"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        start = time.monotonic()
        headers = {"User-Agent": opts.user_agent, "Accept": "text/html,*/*;q=0.8"}
        timeouts = httpx.Timeout(connect=10.0, read=opts.timeout_s, write=10.0, pool=5.0)
        transport = httpx.HTTPTransport(retries=2)
        try:
            with httpx.Client(
                follow_redirects=True,
                max_redirects=10,
                timeout=timeouts,
                headers=headers,
                transport=transport,
            ) as client:
                resp = client.get(url)
                body = resp.content
        except httpx.TooManyRedirects as exc:
            raise RedirectLoopError(str(exc), reason="redirect_loop") from exc
        except httpx.ReadTimeout as exc:
            raise TimeoutError(str(exc), reason="read_timeout") from exc
        except httpx.HTTPError as exc:
            raise FetcherError(str(exc), reason="http_error") from exc

        if len(body) > opts.max_body_bytes:
            raise TooLargeError(
                f"body exceeds cap {opts.max_body_bytes}", reason="too_large"
            )

        elapsed = int((time.monotonic() - start) * 1000)
        return FetcherResult(
            html=body.decode(resp.encoding or "utf-8", errors="replace"),
            final_url=str(resp.url),
            http_status=resp.status_code,
            content_type=resp.headers.get("content-type", ""),
            elapsed_ms=elapsed,
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/integration/test_fast_fetcher.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/fetch/fast.py tests/integration/test_fast_fetcher.py
git commit -m "feat(fetch): FastFetcher (Tier 1) with retries, timeouts, body cap"
```

---

## Task 8: Parse — body (markdown + text)

**Files:**
- Create: `webscraper/parse/__init__.py`
- Create: `webscraper/parse/body.py`
- Test: `tests/unit/parse/__init__.py`
- Test: `tests/unit/parse/test_body.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/parse/test_body.py
"""Body parser tests."""
from webscraper.parse.body import parse_body


def test_parse_body_returns_markdown_and_text_from_article():
    html = """<html><body>
      <h1>My Article</h1>
      <p>This is the lede paragraph with enough prose to clear any
      boilerplate threshold. Claude is a language model.</p>
      <p>Second paragraph, also substantive.</p>
    </body></html>"""
    md, text, title = parse_body(html, requested_url="https://x/y")
    assert "My Article" in md
    assert "lede paragraph" in md
    assert "lede paragraph" in text
    assert "<" not in text  # no HTML tags in text
    assert title == "My Article"


def test_parse_body_returns_empty_strings_for_empty_body():
    md, text, title = parse_body("<html><body></body></html>", requested_url="https://x/y")
    assert md == ""
    assert text == ""
    assert title == ""


def test_parse_body_falls_back_to_readability_when_trafilatura_returns_empty():
    # A minimal non-article page that trafilatura tends to strip completely
    html = "<html><body><div><p>Short note.</p></div></body></html>"
    md, text, _ = parse_body(html, requested_url="https://x/y")
    assert "Short note" in md or "Short note" in text
```

- [ ] **Step 2: Implement `webscraper/parse/__init__.py`** (module stub; real entrypoint in Task 13)

```python
"""Parse subpackage."""
```

- [ ] **Step 3: Implement `webscraper/parse/body.py`**

```python
"""Body parsing: trafilatura → readability-lxml → whole-body fallback."""
from __future__ import annotations

import trafilatura
from readability import Document
from selectolax.parser import HTMLParser
from markdownify import markdownify as md


def _title(tree: HTMLParser) -> str:
    t = tree.css_first("title")
    if t and t.text(strip=True):
        return t.text(strip=True)
    h1 = tree.css_first("h1")
    if h1 and h1.text(strip=True):
        return h1.text(strip=True)
    return ""


def _to_markdown(html_fragment: str) -> str:
    return md(html_fragment, strip=["script", "style"]).strip()


def _to_text(html_fragment: str) -> str:
    tree = HTMLParser(html_fragment)
    return tree.text(deep=True, separator=" ").strip()


def parse_body(html: str, *, requested_url: str) -> tuple[str, str, str]:
    """Return (markdown, text, title) extracted from the given HTML."""
    tree = HTMLParser(html)
    title = _title(tree)

    extracted = trafilatura.extract(
        html, output_format="markdown", include_links=True, include_images=True
    ) or ""
    if extracted.strip():
        text = _to_text(trafilatura.extract(html) or "")
        return extracted.strip(), text, title

    try:
        summary_html = Document(html).summary(html_partial=True)
    except Exception:
        summary_html = ""
    if summary_html:
        return _to_markdown(summary_html), _to_text(summary_html), title

    body = tree.css_first("body")
    if body is None:
        return "", "", title
    body_html = body.html or ""
    return _to_markdown(body_html), _to_text(body_html), title
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/parse/test_body.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/parse/__init__.py webscraper/parse/body.py tests/unit/parse
git commit -m "feat(parse): body extraction with trafilatura → readability fallback"
```

---

## Task 9: Parse — tables

**Files:**
- Create: `webscraper/parse/tables.py`
- Test: `tests/unit/parse/test_tables.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/parse/test_tables.py
"""Table extraction tests."""
from webscraper.parse.tables import extract_tables


def test_extract_tables_with_thead():
    html = """
    <table>
      <thead><tr><th>Name</th><th>Email</th></tr></thead>
      <tbody>
        <tr><td>Alice</td><td>a@x</td></tr>
        <tr><td>Bob</td><td>b@x</td></tr>
      </tbody>
    </table>
    """
    tables = extract_tables(html)
    assert len(tables) == 1
    assert tables[0].headers == ["Name", "Email"]
    assert tables[0].rows == [["Alice", "a@x"], ["Bob", "b@x"]]


def test_extract_tables_without_thead_uses_first_row_of_th():
    html = """
    <table>
      <tr><th>A</th><th>B</th></tr>
      <tr><td>1</td><td>2</td></tr>
    </table>
    """
    tables = extract_tables(html)
    assert tables[0].headers == ["A", "B"]
    assert tables[0].rows == [["1", "2"]]


def test_extract_tables_empty_when_no_tables():
    assert extract_tables("<p>no tables</p>") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/parse/test_tables.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/parse/tables.py
"""Extract <table> elements into TableSpec."""
from selectolax.parser import HTMLParser

from webscraper.envelope import TableSpec


def _cells(row, tag: str) -> list[str]:
    return [c.text(strip=True) for c in row.css(tag)]


def extract_tables(html: str) -> list[TableSpec]:
    tree = HTMLParser(html)
    out: list[TableSpec] = []
    for table in tree.css("table"):
        headers: list[str] = []
        rows: list[list[str]] = []
        thead = table.css_first("thead")
        if thead is not None:
            first_row = thead.css_first("tr")
            if first_row is not None:
                headers = _cells(first_row, "th") or _cells(first_row, "td")
            body_rows = table.css("tbody tr")
        else:
            all_rows = table.css("tr")
            if all_rows and all_rows[0].css("th"):
                headers = _cells(all_rows[0], "th")
                body_rows = all_rows[1:]
            else:
                body_rows = all_rows
        for row in body_rows:
            rows.append(_cells(row, "td"))
        out.append(TableSpec(headers=headers, rows=rows))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/parse/test_tables.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/parse/tables.py tests/unit/parse/test_tables.py
git commit -m "feat(parse): table extraction"
```

---

## Task 10: Parse — forms

**Files:**
- Create: `webscraper/parse/forms.py`
- Test: `tests/unit/parse/test_forms.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/parse/test_forms.py
"""Form extraction tests."""
from webscraper.parse.forms import extract_forms


def test_extract_forms_captures_fields_with_labels():
    html = """
    <form action="/submit" method="POST">
      <label for="q">Search</label>
      <input type="text" id="q" name="q" />
      <textarea name="notes"></textarea>
      <input type="checkbox" name="agree" />
    </form>
    """
    forms = extract_forms(html)
    assert len(forms) == 1
    f = forms[0]
    assert f.action == "/submit"
    assert f.method == "POST"
    names = [x.name for x in f.fields]
    assert names == ["q", "notes", "agree"]
    types = {x.name: x.type for x in f.fields}
    assert types == {"q": "text", "notes": "textarea", "agree": "checkbox"}
    labels = {x.name: x.label for x in f.fields}
    assert labels["q"] == "Search"


def test_extract_forms_defaults_method_to_get():
    html = "<form><input name='x' /></form>"
    assert extract_forms(html)[0].method == "GET"


def test_extract_forms_empty_when_no_forms():
    assert extract_forms("<p>no forms</p>") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/parse/test_forms.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/parse/forms.py
"""Extract <form> elements into FormSpec."""
from selectolax.parser import HTMLParser

from webscraper.envelope import FormField, FormSpec


def _labels_by_for(tree: HTMLParser) -> dict[str, str]:
    out: dict[str, str] = {}
    for lbl in tree.css("label[for]"):
        target = lbl.attributes.get("for") or ""
        if target:
            out[target] = lbl.text(strip=True)
    return out


def extract_forms(html: str) -> list[FormSpec]:
    tree = HTMLParser(html)
    label_map = _labels_by_for(tree)
    out: list[FormSpec] = []
    for form in tree.css("form"):
        fields: list[FormField] = []
        for input_el in form.css("input, textarea, select"):
            tag = (input_el.tag or "").lower()
            name = input_el.attributes.get("name") or ""
            if not name:
                continue
            input_type = (
                "textarea" if tag == "textarea"
                else "select" if tag == "select"
                else (input_el.attributes.get("type") or "text").lower()
            )
            field_id = input_el.attributes.get("id") or ""
            label = label_map.get(field_id, "")
            fields.append(FormField(name=name, type=input_type, label=label))
        action = form.attributes.get("action") or ""
        method = (form.attributes.get("method") or "GET").upper()
        out.append(FormSpec(action=action, method=method, fields=fields))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/parse/test_forms.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/parse/forms.py tests/unit/parse/test_forms.py
git commit -m "feat(parse): form extraction with label matching"
```

---

## Task 11: Parse — images with role classification

**Files:**
- Create: `webscraper/parse/images.py`
- Test: `tests/unit/parse/test_images.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/parse/test_images.py
"""Image extraction and role classification tests."""
from webscraper.parse.images import extract_images


def test_classifies_hero_inline_icon_and_background():
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


def test_empty_when_no_images():
    assert extract_images("<p>nothing</p>", base_url="https://x/") == []


def test_resolves_relative_urls_against_base():
    html = '<img src="foo.png" alt="" />'
    images = extract_images(html, base_url="https://ex.com/a/b/")
    assert images[0].url == "https://ex.com/a/b/foo.png"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/parse/test_images.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/parse/images.py
"""Extract <img> and CSS background-image URLs with role classification."""
import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

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


def _int_attr(el, name: str) -> int:
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
        out.append(ImageSpec(
            url=url,
            alt=img.attributes.get("alt") or "",
            width=width,
            height=height,
            role=_role(width, height, is_background=False),
        ))

    for style_el in tree.css("style"):
        css_text = style_el.text() or ""
        for match in _BG_URL.finditer(css_text):
            out.append(ImageSpec(
                url=urljoin(base_url, match.group(1)),
                role=_role(0, 0, is_background=True),
            ))
    for el in tree.css("[style]"):
        style = el.attributes.get("style") or ""
        for match in _BG_URL.finditer(style):
            out.append(ImageSpec(
                url=urljoin(base_url, match.group(1)),
                role=_role(0, 0, is_background=True),
            ))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/parse/test_images.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/parse/images.py tests/unit/parse/test_images.py
git commit -m "feat(parse): image extraction with role classification"
```

---

## Task 12: Parse — links with kind classification

**Files:**
- Create: `webscraper/parse/links.py`
- Test: `tests/unit/parse/test_links.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/parse/test_links.py
"""Link extraction and kind classification tests."""
from webscraper.parse.links import extract_links


def test_classifies_nav_content_external_anchor():
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


def test_empty_when_no_links():
    assert extract_links("<p>none</p>", base_url="https://ex.com/") == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/parse/test_links.py -v`
Expected: 2 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/parse/links.py
"""Extract <a> links with kind classification."""
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser

from webscraper.envelope import LinkKind, LinkSpec

_NAV_CONTAINERS = ("nav", "header", "footer")


def _is_in_nav(el) -> bool:
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
        out.append(LinkSpec(
            href=resolved,
            text=a.text(strip=True),
            rel=a.attributes.get("rel") or "",
            kind=kind,
        ))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/parse/test_links.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/parse/links.py tests/unit/parse/test_links.py
git commit -m "feat(parse): link extraction with kind classification"
```

---

## Task 13: Parse aggregator (`HtmlParser.parse`)

**Files:**
- Modify: `webscraper/parse/__init__.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/parse/test_body.py`:
```python
# ... existing imports ...
from datetime import datetime, timezone

from webscraper.envelope import FetchResult
from webscraper.fetch.base import FetcherResult
from webscraper.parse import parse_to_envelope


def test_parse_to_envelope_produces_valid_fetch_result():
    html = "<html><head><title>T</title></head><body><p>Body.</p></body></html>"
    fetcher_result = FetcherResult(
        html=html,
        final_url="https://example.com/p",
        http_status=200,
        content_type="text/html",
        elapsed_ms=100,
    )
    from webscraper.envelope import TierAttempt
    envelope = parse_to_envelope(
        fetcher_result,
        requested_url="https://example.com/p",
        tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=100)],
        now=datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc),
    )
    assert isinstance(envelope, FetchResult)
    assert envelope.title == "T"
    assert "Body" in envelope.markdown
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/parse/test_body.py::test_parse_to_envelope_produces_valid_fetch_result -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/parse/__init__.py
"""Parse subpackage — aggregates all HTML extractors into FetchResult."""
from datetime import datetime, timezone

from webscraper.envelope import FetchResult, Meta, TierAttempt
from webscraper.fetch.base import FetcherResult
from webscraper.parse.body import parse_body
from webscraper.parse.forms import extract_forms
from webscraper.parse.images import extract_images
from webscraper.parse.links import extract_links
from webscraper.parse.tables import extract_tables


def parse_to_envelope(
    fr: FetcherResult,
    *,
    requested_url: str,
    tier_history: list[TierAttempt],
    now: datetime | None = None,
) -> FetchResult:
    """Turn a raw fetcher result + tier history into a canonical envelope."""
    markdown, text, title = parse_body(fr.html, requested_url=requested_url)
    tables = extract_tables(fr.html)
    forms = extract_forms(fr.html)
    images = extract_images(fr.html, base_url=fr.final_url)
    links = extract_links(fr.html, base_url=fr.final_url)
    tier_used = tier_history[-1].tier
    meta = Meta(
        tier_used=tier_used,
        tier_history=tier_history,
        http_status=fr.http_status,
        content_type=fr.content_type,
    )
    return FetchResult(
        url=requested_url,
        final_url=fr.final_url,
        fetched_at=(now or datetime.now(tz=timezone.utc)),
        meta=meta,
        title=title,
        markdown=markdown,
        text=text,
        tables=tables,
        forms=forms,
        images=images,
        links=links,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/parse -v`
Expected: all parse unit tests PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/parse/__init__.py tests/unit/parse/test_body.py
git commit -m "feat(parse): aggregate parsers into parse_to_envelope"
```

---

## Task 14: Challenge-page fingerprints

**Files:**
- Create: `webscraper/challenge.py`
- Test: `tests/unit/test_challenge.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_challenge.py
"""Anti-bot challenge-page detection."""
from webscraper.challenge import is_challenge_page


def test_detects_cloudflare_iuam():
    html = '<div class="cf-browser-verification">Checking your browser...Cloudflare</div>'
    detected, reason = is_challenge_page(html)
    assert detected is True
    assert "cloudflare" in reason.lower()


def test_detects_perimeterx_by_phrase():
    html = "<html><body>Please verify you are a human. PerimeterX</body></html>"
    detected, reason = is_challenge_page(html)
    assert detected is True
    assert "perimeterx" in reason.lower()


def test_detects_akamai_block_page():
    html = "<p>Access denied — Reference #18.abc.1234567890.12345</p>"
    detected, reason = is_challenge_page(html)
    assert detected is True
    assert "akamai" in reason.lower()


def test_passes_normal_content():
    html = "<html><body><h1>Article</h1><p>Lots of real content here.</p></body></html>"
    detected, _ = is_challenge_page(html)
    assert detected is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_challenge.py -v`
Expected: 4 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/challenge.py
"""Challenge-page fingerprinting (Cloudflare IUAM, PerimeterX, Akamai)."""
import re

_FINGERPRINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cloudflare", re.compile(r"cf-browser-verification|Checking your browser.+Cloudflare", re.I | re.S)),
    ("perimeterx", re.compile(r"PerimeterX|verify you are a human", re.I)),
    ("akamai", re.compile(r"Reference #\d+\.[a-f0-9]+\.\d+\.\w+|Access Denied.*Akamai", re.I | re.S)),
)


def is_challenge_page(html: str) -> tuple[bool, str]:
    for name, pattern in _FINGERPRINTS:
        if pattern.search(html):
            return True, f"challenge:{name}"
    return False, ""
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_challenge.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/challenge.py tests/unit/test_challenge.py
git commit -m "feat(challenge): fingerprint detector for bot-protection pages"
```

---

## Task 15: Dispatcher with escalation rule

**Files:**
- Create: `webscraper/fetch/dispatcher.py`
- Test: `tests/unit/fetch/__init__.py`
- Test: `tests/unit/fetch/test_dispatcher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/fetch/test_dispatcher.py
"""Dispatcher escalation tests using mocked Fetchers."""
from dataclasses import dataclass

import pytest

from webscraper.envelope import FetchResult
from webscraper.errors import AllTiersFailedError, FetcherError
from webscraper.fetch.base import FetchOptions, FetcherResult
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions


@dataclass
class _MockFetcher:
    name: str
    result: FetcherResult | None = None
    exc: Exception | None = None

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


_OK_LONG = "<html><head><title>ok</title></head><body>" + ("<p>lorem ipsum " * 80) + "</p></body></html>"
_EMPTY = "<html><body></body></html>"


def _fr(html: str, status: int = 200) -> FetcherResult:
    return FetcherResult(html=html, final_url="https://ex/y", http_status=status, content_type="text/html", elapsed_ms=10)


def test_auto_escalates_when_first_tier_returns_empty():
    d = Dispatcher([_MockFetcher("fast", result=_fr(_EMPTY)), _MockFetcher("browser", result=_fr(_OK_LONG))])
    env = d.run("https://ex/y", DispatchOptions(auto_escalate=True))
    assert env.meta.tier_used == "browser"
    assert [t.tier for t in env.meta.tier_history] == ["fast", "browser"]
    assert env.meta.tier_history[0].outcome == "escalated"
    assert env.meta.tier_history[1].outcome == "success"


def test_auto_escalates_on_fetcher_exception():
    d = Dispatcher([_MockFetcher("fast", exc=FetcherError("boom", reason="http_error")),
                    _MockFetcher("browser", result=_fr(_OK_LONG))])
    env = d.run("https://ex/y", DispatchOptions(auto_escalate=True))
    assert env.meta.tier_used == "browser"


def test_explicit_tier_disables_escalation():
    d = Dispatcher([_MockFetcher("fast", result=_fr(_EMPTY)), _MockFetcher("browser", result=_fr(_OK_LONG))])
    with pytest.raises(AllTiersFailedError):
        d.run("https://ex/y", DispatchOptions(auto_escalate=False, forced_tier="fast"))


def test_challenge_page_marks_tier_unacceptable():
    challenge = '<html><body><div class="cf-browser-verification">Checking your browser...Cloudflare</div></body></html>'
    d = Dispatcher([_MockFetcher("fast", result=_fr(challenge)), _MockFetcher("browser", result=_fr(_OK_LONG))])
    env = d.run("https://ex/y", DispatchOptions(auto_escalate=True))
    assert env.meta.tier_history[0].reason.startswith("challenge:")
    assert env.meta.tier_used == "browser"


def test_all_tiers_failing_raises():
    d = Dispatcher([_MockFetcher("fast", result=_fr(_EMPTY)), _MockFetcher("browser", result=_fr(_EMPTY))])
    with pytest.raises(AllTiersFailedError):
        d.run("https://ex/y", DispatchOptions(auto_escalate=True))
```

Also create `tests/unit/fetch/__init__.py` with `"""Fetch unit tests."""`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/fetch/test_dispatcher.py -v`
Expected: 5 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/fetch/dispatcher.py
"""Tier dispatcher with escalation rule."""
from __future__ import annotations

from dataclasses import dataclass

from webscraper.challenge import is_challenge_page
from webscraper.envelope import FetchResult, TierAttempt, TierName
from webscraper.errors import AllTiersFailedError, FetcherError
from webscraper.fetch.base import FetchOptions, Fetcher, FetcherResult
from webscraper.log import get_logger
from webscraper.parse import parse_to_envelope

_log = get_logger("dispatcher")


@dataclass(frozen=True)
class DispatchOptions:
    auto_escalate: bool = True
    forced_tier: TierName | None = None
    min_content_chars: int = 200
    fetch_opts: FetchOptions = FetchOptions()


class Dispatcher:
    def __init__(self, fetchers: list[Fetcher]) -> None:
        self._fetchers = fetchers

    def run(self, url: str, opts: DispatchOptions) -> FetchResult:
        chain = self._build_chain(opts)
        history: list[TierAttempt] = []
        last_good: tuple[FetcherResult, FetchResult] | None = None

        for fetcher in chain:
            _log.info("tier_attempt_start", extra={"tier": fetcher.name, "url": url})
            try:
                fr = fetcher.fetch(url, opts.fetch_opts)
            except FetcherError as exc:
                history.append(TierAttempt(
                    tier=fetcher.name, outcome="escalated",
                    elapsed_ms=0, reason=exc.reason,
                ))
                continue

            tmp_history = history + [TierAttempt(
                tier=fetcher.name, outcome="success", elapsed_ms=fr.elapsed_ms,
            )]
            envelope = parse_to_envelope(
                fr, requested_url=url, tier_history=tmp_history,
            )

            reason = self._unacceptable_reason(fr, envelope, opts.min_content_chars)
            if reason is None:
                history.append(tmp_history[-1])
                return envelope.model_copy(update={"meta": envelope.meta.model_copy(
                    update={"tier_history": history, "tier_used": fetcher.name}
                )})

            history.append(TierAttempt(
                tier=fetcher.name, outcome="escalated",
                elapsed_ms=fr.elapsed_ms, reason=reason,
            ))
            last_good = (fr, envelope)

        raise AllTiersFailedError(
            f"all tiers failed: {[t.reason or t.outcome for t in history]}"
        )

    def _build_chain(self, opts: DispatchOptions) -> list[Fetcher]:
        if opts.forced_tier is not None:
            return [f for f in self._fetchers if f.name == opts.forced_tier]
        if not opts.auto_escalate:
            return self._fetchers[:1]
        return list(self._fetchers)

    @staticmethod
    def _unacceptable_reason(
        fr: FetcherResult, envelope: FetchResult, min_chars: int
    ) -> str | None:
        if not (200 <= fr.http_status < 300):
            return f"http_{fr.http_status}"
        detected, reason = is_challenge_page(fr.html)
        if detected:
            return reason
        if len(envelope.markdown) < min_chars:
            return "insufficient_content"
        return None
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/fetch -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/fetch/dispatcher.py tests/unit/fetch
git commit -m "feat(fetch): dispatcher with auto-escalation and forced tier"
```

---

## Task 16: Chrome profile copy

**Files:**
- Create: `webscraper/profile.py`
- Test: `tests/unit/test_profile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_profile.py
"""Chrome profile copy tests."""
from pathlib import Path

import pytest

from webscraper.errors import EnvironmentError
from webscraper.profile import copy_profile, locate_profile


def test_locate_profile_uses_env_override(tmp_path, monkeypatch):
    fake = tmp_path / "CustomProfile"
    fake.mkdir()
    monkeypatch.setenv("WEBSCRAPER_CHROME_PROFILE", str(fake))
    assert locate_profile() == fake


def test_locate_profile_raises_when_env_points_nowhere(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBSCRAPER_CHROME_PROFILE", str(tmp_path / "missing"))
    with pytest.raises(EnvironmentError):
        locate_profile()


def test_copy_profile_copies_files_but_skips_lock_files(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "Cookies").write_bytes(b"cookies-db")
    (src / "SingletonLock").symlink_to(src / "whatever")  # lock file
    (src / "LOCK").write_bytes(b"lock")
    dst_parent = tmp_path / "dst"
    dst_parent.mkdir()
    with copy_profile(src, tmp_parent=dst_parent) as copied:
        assert (copied / "Cookies").read_bytes() == b"cookies-db"
        assert not (copied / "SingletonLock").exists()
        assert not (copied / "LOCK").exists()
    # Cleanup on exit
    assert not copied.exists()


def test_copy_profile_cleans_up_on_exception(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "Cookies").write_bytes(b"x")
    dst_parent = tmp_path / "dst"
    dst_parent.mkdir()
    copied_path: Path | None = None
    with pytest.raises(RuntimeError):
        with copy_profile(src, tmp_parent=dst_parent) as copied:
            copied_path = copied
            raise RuntimeError("boom")
    assert copied_path is not None
    assert not copied_path.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_profile.py -v`
Expected: 4 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/profile.py
"""Chrome profile discovery and copy-on-run isolation."""
from __future__ import annotations

import os
import platform
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from webscraper.errors import EnvironmentError

_LOCK_NAMES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "LOCK", "lockfile"}


def _default_profile_path() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library/Application Support/Google/Chrome/Default"
    if system == "Linux":
        return home / ".config/google-chrome/Default"
    raise EnvironmentError(f"unsupported platform: {system}")


def locate_profile() -> Path:
    override = os.environ.get("WEBSCRAPER_CHROME_PROFILE")
    if override:
        path = Path(override)
        if not path.exists() or not path.is_dir():
            raise EnvironmentError(f"WEBSCRAPER_CHROME_PROFILE does not point to a directory: {path}")
        return path
    path = _default_profile_path()
    if not path.exists():
        raise EnvironmentError(f"Chrome profile not found at {path}")
    return path


def _ignore_locks(dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n in _LOCK_NAMES]


@contextmanager
def copy_profile(src: Path, *, tmp_parent: Path | None = None) -> Iterator[Path]:
    """Copy a Chrome profile to a scratch directory; clean up on exit."""
    parent = tmp_parent or Path(tempfile.gettempdir())
    dst = Path(tempfile.mkdtemp(prefix="webscraper-profile-", dir=str(parent)))
    try:
        shutil.copytree(src, dst / "profile", ignore=_ignore_locks, dirs_exist_ok=False)
        yield dst / "profile"
    finally:
        shutil.rmtree(dst, ignore_errors=True)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_profile.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/profile.py tests/unit/test_profile.py
git commit -m "feat(profile): Chrome profile locate + copy-on-run with cleanup"
```

---

## Task 17: BrowserFetcher (Tier 2)

**Files:**
- Create: `webscraper/fetch/browser.py`
- Test: `tests/integration/test_browser_fetcher.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_browser_fetcher.py
"""BrowserFetcher (Playwright) integration tests."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from webscraper.fetch.base import FetchOptions
from webscraper.fetch.browser import BrowserFetcher


@pytest.fixture
def seeded_profile(tmp_path: Path, fixture_server: str) -> Path:
    """Boot Playwright once to log in, then return the profile dir to reuse."""
    profile = tmp_path / "chrome-seeded"
    profile.mkdir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
        finally:
            ctx.close()
    return profile


def test_browser_renders_spa_content(fixture_server: str, tmp_path: Path) -> None:
    f = BrowserFetcher()
    profile = tmp_path / "empty-profile"
    profile.mkdir()
    result = f.fetch(
        f"{fixture_server}/spa/app",
        FetchOptions(chrome_profile_path=str(profile)),
    )
    assert result.http_status == 200
    assert "SPA Rendered" in result.html


def test_browser_reads_auth_cookie_from_copied_profile(
    fixture_server: str, seeded_profile: Path
) -> None:
    f = BrowserFetcher()
    result = f.fetch(
        f"{fixture_server}/auth/private",
        FetchOptions(chrome_profile_path=str(seeded_profile)),
    )
    assert result.http_status == 200
    assert "Authenticated Content" in result.html
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_browser_fetcher.py -v`
Expected: 2 FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# webscraper/fetch/browser.py
"""Tier 2 fetcher: Playwright with a copied Chrome profile."""
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright

from webscraper.errors import EnvironmentError, FetcherError, TimeoutError
from webscraper.fetch.base import FetchOptions, FetcherResult
from webscraper.profile import copy_profile, locate_profile


class BrowserFetcher:
    name = "browser"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        profile_src = Path(opts.chrome_profile_path) if opts.chrome_profile_path else locate_profile()
        start = time.monotonic()
        with copy_profile(profile_src) as scratch:
            try:
                with sync_playwright() as p:
                    ctx = p.chromium.launch_persistent_context(
                        str(scratch), headless=True, channel="chrome",
                    )
                    try:
                        page = ctx.new_page()
                        try:
                            response = page.goto(
                                url,
                                wait_until="networkidle",
                                timeout=int(opts.timeout_s * 1000),
                            )
                        except PWTimeoutError as exc:
                            raise TimeoutError(str(exc), reason="browser_timeout") from exc
                        if response is None:
                            raise FetcherError("no response from navigation", reason="no_response")
                        html = page.content()
                        final_url = page.url
                        status = response.status
                        content_type = response.header_value("content-type") or ""
                    finally:
                        ctx.close()
            except (FetcherError, TimeoutError):
                raise
            except Exception as exc:
                raise EnvironmentError(f"Playwright launch failed: {exc}") from exc
        elapsed = int((time.monotonic() - start) * 1000)
        return FetcherResult(
            html=html,
            final_url=final_url,
            http_status=status,
            content_type=content_type,
            elapsed_ms=elapsed,
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_browser_fetcher.py -v`
Expected: 2 PASS. (Requires `playwright install chromium` from Task 1.)

- [ ] **Step 5: Commit**

```bash
git add webscraper/fetch/browser.py tests/integration/test_browser_fetcher.py
git commit -m "feat(fetch): BrowserFetcher (Tier 2) with profile copy-on-run"
```

---

## Task 18: Renderers — markdown and html

**Files:**
- Create: `webscraper/render/__init__.py`
- Create: `webscraper/render/markdown.py`
- Create: `webscraper/render/html.py`
- Test: `tests/unit/render/__init__.py`
- Test: `tests/unit/render/test_markdown.py`
- Test: `tests/unit/render/test_html.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/render/test_markdown.py
"""Markdown renderer tests."""
from datetime import datetime, timezone

from webscraper.envelope import FetchResult, Meta, TierAttempt
from webscraper.render.markdown import render_markdown


def _envelope(markdown: str = "# Hello\n\nBody.", title: str = "Hello") -> FetchResult:
    return FetchResult(
        url="https://x/y", final_url="https://x/y",
        fetched_at=datetime(2026, 4, 16, tzinfo=timezone.utc),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200, content_type="text/html",
        ),
        title=title, markdown=markdown, text="Body.",
    )


def test_render_markdown_returns_body_markdown():
    out = render_markdown(_envelope())
    assert out.startswith("# Hello")
    assert "Body." in out
```

```python
# tests/unit/render/test_html.py
"""HTML renderer tests."""
from datetime import datetime, timezone

from webscraper.envelope import FetchResult, Meta, TierAttempt
from webscraper.render.html import render_html


def _envelope() -> FetchResult:
    return FetchResult(
        url="https://x/y", final_url="https://x/y",
        fetched_at=datetime(2026, 4, 16, tzinfo=timezone.utc),
        meta=Meta(
            tier_used="fast",
            tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
            http_status=200, content_type="text/html",
        ),
        title="My Title", markdown="# H\n\nBody.", text="Body.",
    )


def test_render_html_is_self_contained_document():
    html = render_html(_envelope())
    assert html.startswith("<!doctype html>")
    assert "<title>My Title</title>" in html
    assert "<h1>H</h1>" in html
    assert "Body." in html
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/render -v`
Expected: 2 FAIL.

- [ ] **Step 3: Implement**

```python
# webscraper/render/__init__.py
"""Renderer subpackage."""
```

```python
# webscraper/render/markdown.py
"""Render an envelope as markdown."""
from webscraper.envelope import FetchResult


def render_markdown(envelope: FetchResult) -> str:
    return envelope.markdown
```

```python
# webscraper/render/html.py
"""Render an envelope as a self-contained HTML preview."""
import html as htmllib

import markdown as md_lib

from webscraper.envelope import FetchResult


def render_html(envelope: FetchResult) -> str:
    title = htmllib.escape(envelope.title or envelope.url)
    body_html = md_lib.markdown(envelope.markdown, extensions=["extra", "sane_lists"])
    return (
        "<!doctype html>\n"
        f"<html><head><meta charset=\"utf-8\"><title>{title}</title></head>"
        f"<body>{body_html}</body></html>"
    )
```

Also add `markdown` to `pyproject.toml` dependencies:
```toml
"markdown>=3.7",
```

- [ ] **Step 4: Refresh deps and run tests**

Run: `uv sync && uv run pytest tests/unit/render -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/render tests/unit/render pyproject.toml uv.lock
git commit -m "feat(render): markdown and html renderers off envelope"
```

---

## Task 19: CLI — `fetch` subcommand

**Files:**
- Modify: `webscraper/cli.py`
- Test: `tests/integration/test_cli_fetch.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_cli_fetch.py
"""CLI integration tests for `webscraper fetch`."""
import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True, text=True, timeout=60,
    )


def test_fetch_static_emits_valid_envelope(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast")
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["meta"]["tier_used"] == "fast"
    assert "Static Article" in envelope["title"]
    assert "lazy brown fox" in envelope["markdown"].lower()


def test_fetch_malformed_url_exits_3() -> None:
    result = _run("fetch", "not-a-url")
    assert result.returncode == 3


def test_fetch_render_markdown_switches_stdout(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast", "--render=markdown")
    assert result.returncode == 0
    assert not result.stdout.lstrip().startswith("{")
    assert "Static Article" in result.stdout


def test_fetch_out_writes_file(fixture_server: str, tmp_path) -> None:
    out_file = tmp_path / "result.json"
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast", "--out", str(out_file))
    assert result.returncode == 0
    data = json.loads(out_file.read_text())
    assert data["title"] == "Static Article"


def test_fetch_explicit_tier_failure_exits_2(fixture_server: str) -> None:
    # `/spa/app` returns near-empty content on Tier 1; forcing tier=fast with
    # default threshold should be unacceptable and exit 2.
    result = _run("fetch", f"{fixture_server}/spa/app", "--tier=fast")
    assert result.returncode == 2
    err = json.loads(result.stdout)
    assert "error" in err
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_cli_fetch.py -v`
Expected: 5 FAIL.

- [ ] **Step 3: Implement `webscraper/cli.py`**

```python
# webscraper/cli.py
"""CLI entrypoint for webscraper."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from webscraper import __version__
from webscraper.envelope import FetchResult
from webscraper.errors import (
    AllTiersFailedError,
    EnvironmentError as WSEnvironmentError,
    UsageError,
)
from webscraper.fetch.base import FetchOptions
from webscraper.fetch.browser import BrowserFetcher
from webscraper.fetch.dispatcher import Dispatcher, DispatchOptions
from webscraper.fetch.fast import FastFetcher
from webscraper.log import configure as configure_logging
from webscraper.log import get_logger
from webscraper.render.html import render_html
from webscraper.render.markdown import render_markdown

_log = get_logger("cli")

EXIT_OK = 0
EXIT_FETCH_FAIL = 2
EXIT_USAGE = 3
EXIT_ENV = 4


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="webscraper")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch a single URL")
    fetch.add_argument("url")
    fetch.add_argument("--tier", choices=["fast", "browser", "firecrawl"])
    fetch.add_argument("--render", choices=["json", "markdown", "html"], default="json")
    fetch.add_argument("--out", type=Path)
    fetch.add_argument("--log-file", type=Path)
    fetch.add_argument("--min-content-chars", type=int, default=200)
    fetch.add_argument("--timeout", type=float, default=30.0)
    fetch.add_argument("--quiet", action="store_true")

    sub.add_parser("doctor", help="environment health check")

    return p


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise UsageError(f"malformed URL: {url}")


def _configure_logs(args: argparse.Namespace) -> None:
    level = "ERROR" if getattr(args, "quiet", False) else "INFO"
    stream = open(args.log_file, "a") if getattr(args, "log_file", None) else None
    configure_logging(level=level, stream=stream)


def _run_fetch(args: argparse.Namespace) -> int:
    _validate_url(args.url)
    dispatcher = Dispatcher([FastFetcher(), BrowserFetcher()])
    opts = DispatchOptions(
        auto_escalate=args.tier is None,
        forced_tier=args.tier,
        min_content_chars=args.min_content_chars,
        fetch_opts=FetchOptions(timeout_s=args.timeout),
    )
    envelope = dispatcher.run(args.url, opts)
    _emit(envelope, args)
    return EXIT_OK


def _emit(envelope: FetchResult, args: argparse.Namespace) -> None:
    if args.render == "json":
        payload = envelope.model_dump_json(indent=2)
    elif args.render == "markdown":
        payload = render_markdown(envelope)
    else:  # html
        payload = render_html(envelope)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")


def _emit_error(kind: str, message: str, extra: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"error": {"type": kind, "message": message}}
    if extra:
        payload["error"].update(extra)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _configure_logs(args)
    try:
        if args.command == "fetch":
            return _run_fetch(args)
        if args.command == "doctor":
            from webscraper.doctor import run_doctor
            return run_doctor()
        parser.print_help()
        return EXIT_USAGE
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except WSEnvironmentError as exc:
        _emit_error("environment", str(exc))
        return EXIT_ENV
    except AllTiersFailedError as exc:
        _emit_error("fetch_failed", str(exc))
        return EXIT_FETCH_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_cli_fetch.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/cli.py tests/integration/test_cli_fetch.py
git commit -m "feat(cli): fetch subcommand with render, --out, exit codes"
```

---

## Task 20: CLI — `doctor` subcommand

**Files:**
- Create: `webscraper/doctor.py`
- Test: `tests/integration/test_cli_doctor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/integration/test_cli_doctor.py
"""CLI integration tests for `webscraper doctor`."""
import subprocess
import sys


def test_doctor_runs_and_exits_cleanly():
    result = subprocess.run(
        [sys.executable, "-m", "webscraper", "doctor"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode in (0, 4)  # 0 if healthy, 4 if env incomplete
    assert "Python" in result.stdout
    assert "Playwright" in result.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_cli_doctor.py -v`
Expected: 1 FAIL (doctor module missing).

- [ ] **Step 3: Implement**

```python
# webscraper/doctor.py
"""Environment health check."""
from __future__ import annotations

import importlib
import platform
import sys

from webscraper.errors import EnvironmentError
from webscraper.profile import locate_profile

_OK = "  OK"
_FAIL = "FAIL"


def _check_python() -> tuple[str, bool]:
    return f"Python {platform.python_version()} ({sys.executable})", sys.version_info >= (3, 11)


def _check_playwright() -> tuple[str, bool]:
    try:
        importlib.import_module("playwright")
    except ImportError:
        return "Playwright: not installed", False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser_path = p.chromium.executable_path
        return f"Playwright Chromium at {browser_path}", True
    except Exception as exc:
        return f"Playwright: {exc}", False


def _check_profile() -> tuple[str, bool]:
    try:
        path = locate_profile()
    except EnvironmentError as exc:
        return f"Chrome profile: {exc}", False
    return f"Chrome profile at {path}", True


def run_doctor() -> int:
    checks = [_check_python(), _check_playwright(), _check_profile()]
    all_ok = True
    for message, ok in checks:
        mark = _OK if ok else _FAIL
        print(f"[{mark}] {message}")
        all_ok = all_ok and ok
    return 0 if all_ok else 4
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/integration/test_cli_doctor.py -v`
Expected: 1 PASS.

- [ ] **Step 5: Commit**

```bash
git add webscraper/doctor.py tests/integration/test_cli_doctor.py
git commit -m "feat(cli): doctor subcommand for environment health checks"
```

---

## Task 21: Populate FUNCTIONAL-REQUIREMENTS.md

**Files:**
- Modify: `FUNCTIONAL-REQUIREMENTS.md`

- [ ] **Step 1: Append the 15 requirements to the table**

Replace the existing `## Requirements` section with:

```markdown
## Requirements

| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-001 | fetch | Static page returns valid envelope via Tier 1 | response |
| F-REQ-002 | fetch | JS-rendered page escalates Tier 1 → Tier 2 and returns rendered content | response |
| F-REQ-003 | fetch | Login-gated page is retrievable via copied Chrome profile | response |
| F-REQ-004 | fetch | `--tier` override is honored; no silent escalation | response |
| F-REQ-005 | content | Tables surface as `{headers, rows}` | response |
| F-REQ-006 | content | Forms surface as `{action, method, fields[]}` | response |
| F-REQ-007 | content | Images surface as `{url, alt, width, height, role}` | response |
| F-REQ-008 | content | Links classified as `nav/content/external/anchor` | response |
| F-REQ-009 | render | `--render=markdown` emits markdown, not JSON | response |
| F-REQ-010 | render | `--render=html` emits valid self-contained HTML | response |
| F-REQ-011 | security | No cookies or profile bytes appear in stdout/stderr/logs | response |
| F-REQ-012 | security | Scratch profile directory is removed on exit (success and failure) | response |
| F-REQ-013 | errors | Malformed URL (parse error) exits non-zero with a diagnostic JSON error | response |
| F-REQ-014 | errors | Network-unreachable host exits non-zero with a diagnostic JSON error | response |
| F-REQ-015 | errors | All enabled tiers failing exits non-zero with a diagnostic including full `tier_history` | response |
```

- [ ] **Step 2: Commit**

```bash
git add FUNCTIONAL-REQUIREMENTS.md
git commit -m "docs: register 15 F-REQ entries for v0.1"
```

---

## Task 22: E2E test suite tagged `[F-REQ-xxx]`

**Files:**
- Create: `tests/e2e/__init__.py` (if not present from Task 1)
- Create: `tests/e2e/test_fetch_flows.py`

- [ ] **Step 1: Write the full tagged E2E suite**

```python
# tests/e2e/test_fetch_flows.py
"""End-to-end tests driving the real CLI against the fixture server.

Every test below is tagged with a `[F-REQ-xxx]` comment matching an entry
in `FUNCTIONAL-REQUIREMENTS.md`; `check-functional-coverage.sh` relies on
these tags to enforce coverage.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True, text=True, timeout=90, env=full_env,
    )


def _envelope(stdout: str) -> dict:
    return json.loads(stdout)


# [F-REQ-001]
def test_static_page_via_tier1(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    assert envelope["meta"]["tier_used"] == "fast"
    assert "Static Article" in envelope["title"]


# [F-REQ-002]
def test_spa_escalates_to_tier2(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/spa/app")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    assert envelope["meta"]["tier_used"] == "browser"
    history = envelope["meta"]["tier_history"]
    assert history[0]["tier"] == "fast"
    assert history[0]["outcome"] == "escalated"
    assert "SPA Rendered" in envelope["markdown"] or "SPA Rendered" in envelope["text"]


# [F-REQ-003]
def test_auth_gated_page_via_copied_profile(fixture_server: str, tmp_path: Path) -> None:
    # Seed a headless Chrome profile with the fixture auth cookie
    profile = tmp_path / "auth-profile"
    profile.mkdir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
        finally:
            ctx.close()
    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_CHROME_PROFILE": str(profile)},
    )
    assert result.returncode == 0, result.stderr
    envelope = _envelope(result.stdout)
    assert "Authenticated Content" in envelope["markdown"] or "Authenticated" in envelope["text"]


# [F-REQ-004]
def test_explicit_tier_disables_escalation(fixture_server: str) -> None:
    # /spa/app returns near-empty content on Tier 1; explicit tier should not escalate.
    result = _run("fetch", f"{fixture_server}/spa/app", "--tier=fast")
    assert result.returncode == 2
    err = _envelope(result.stdout)
    assert err["error"]["type"] == "fetch_failed"


# [F-REQ-005]
def test_tables_structured(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/table/large", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    tables = envelope["tables"]
    assert tables[0]["headers"] == ["Name", "Email"]
    assert ["Alice", "alice@example.com"] in tables[0]["rows"]


# [F-REQ-006]
def test_forms_structured(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/forms/login", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    form = envelope["forms"][0]
    assert form["method"] == "POST"
    names = [f["name"] for f in form["fields"]]
    assert names == ["q", "opt", "notes", "agree"]


# [F-REQ-007]
def test_images_structured(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/images/mixed", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    roles = {img["url"].split("/")[-1]: img["role"] for img in envelope["images"]}
    assert roles["hero.jpg"] == "hero"
    assert roles["icon.png"] == "icon"
    assert roles["bg.jpg"] == "background"


# [F-REQ-008]
def test_links_classified(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/links/mixed", "--tier=fast")
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    kinds = {link["text"]: link["kind"] for link in envelope["links"]}
    assert kinds["Home"] == "nav"
    assert kinds["here"] == "content"
    assert kinds["external"] == "external"
    assert kinds["section 2"] == "anchor"


# [F-REQ-009]
def test_render_markdown(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast", "--render=markdown")
    assert result.returncode == 0
    assert not result.stdout.lstrip().startswith("{")
    assert "Static Article" in result.stdout


# [F-REQ-010]
def test_render_html(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/static/article", "--tier=fast", "--render=html")
    assert result.returncode == 0
    assert result.stdout.lstrip().startswith("<!doctype html>")
    assert "<title>Static Article</title>" in result.stdout


# [F-REQ-011]
def test_no_cookies_or_profile_bytes_in_stdout(
    fixture_server: str, tmp_path: Path
) -> None:
    profile = tmp_path / "auth-profile"
    profile.mkdir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(profile), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
        finally:
            ctx.close()
    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_CHROME_PROFILE": str(profile)},
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "fixture_auth" not in combined
    assert "Cookies" not in combined


# [F-REQ-012]
def test_scratch_profile_cleaned_up_after_run(
    fixture_server: str, tmp_path: Path
) -> None:
    import tempfile
    before = set(Path(tempfile.gettempdir()).glob("webscraper-profile-*"))
    profile = tmp_path / "p"
    profile.mkdir()
    result = _run(
        "fetch", f"{fixture_server}/spa/app", "--tier=browser",
        env={"WEBSCRAPER_CHROME_PROFILE": str(profile)},
    )
    assert result.returncode == 0
    after = set(Path(tempfile.gettempdir()).glob("webscraper-profile-*"))
    assert after <= before  # no new scratch dirs left behind


# [F-REQ-013]
def test_malformed_url_exits_3() -> None:
    result = _run("fetch", "ftp://nope", "--tier=fast")
    assert result.returncode == 3


# [F-REQ-014]
def test_network_unreachable_exits_2() -> None:
    result = _run("fetch", "http://127.0.0.1:1/never", "--tier=fast")
    assert result.returncode == 2
    err = _envelope(result.stdout)
    assert err["error"]["type"] == "fetch_failed"


# [F-REQ-015]
def test_all_tiers_fail_includes_history(fixture_server: str) -> None:
    result = _run("fetch", f"{fixture_server}/challenge/cloudflare")
    # Tier 1 + Tier 2 will both return the challenge page; no Tier 3 in v0.1.
    assert result.returncode == 2
    err = _envelope(result.stdout)
    assert err["error"]["type"] == "fetch_failed"
```

- [ ] **Step 2: Run the E2E suite**

Run: `uv run pytest tests/e2e -v`
Expected: all 15 tests PASS. Some may be slow (Tier 2 Playwright); budget ~90s.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_fetch_flows.py
git commit -m "test(e2e): 15 F-REQ-tagged end-to-end tests"
```

---

## Task 23: Full verify.sh and functional-coverage check

**Files:** (no file changes — this is a validation task)

- [ ] **Step 1: Run the full suite**

Run: `./scripts/verify.sh`
Expected: all language gates green (ruff, mypy, pytest), security gate green, functional-coverage check green (0 uncovered / 0 orphans / 0 untagged).

- [ ] **Step 2: If anything fails, fix in place**

If `ruff` flags style: `uv run ruff format . && uv run ruff check . --fix`.
If `mypy` flags types: add types or `# type: ignore[<code>]` with a reason comment at the specific line (never blanket ignore).
If `pytest` flags failures: read the assertion; do NOT modify the test to pass — fix the implementation.
If functional coverage flags orphans: delete the orphaned tag OR add an F-REQ row.

Re-run `./scripts/verify.sh` after each fix.

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: verify.sh green"
```

(If no fixes needed, skip the commit.)

---

## Task 24: ADR-001 — tiered fetcher

**Files:**
- Create: `docs/ADR/ADR-001-tiered-fetcher.md`

- [ ] **Step 1: Write the ADR**

```markdown
# ADR-001: Tiered fetcher architecture (Option A — monolithic CLI)

**Status:** Accepted (2026-04-16)

## Context

webScraper needs to retrieve arbitrary web pages for Claude Code, across three regimes:
- static HTML (fast, free)
- JS-rendered / auth-gated pages (slower, free but needs a browser)
- anti-bot-protected pages (paid, via Firecrawl, planned for v0.3)

`docs/ARCH.md § 2` considers three architectures:
- **A.** Monolithic CLI with backends behind a `Fetcher` Protocol.
- **B.** Multi-process: orchestrator shells out to tier-specific subprocesses.
- **C.** Library + thin CLI + future MCP server.

## Decision

Adopt **Option A**. Backends are classes implementing a `Fetcher` Protocol; the Dispatcher enforces escalation. No subprocess boundary between tiers.

## Consequences

**Positive:**
- Simplest to build, test, and debug.
- Clean seams via Protocol; backends remain interchangeable.
- Lowest IPC overhead.

**Negative:**
- A Playwright crash can take down the whole run.
- Playwright's memory cost is imported into every run (mitigated by lazy import inside `BrowserFetcher`).

**Revisited when:**
- Playwright crashes are observed to affect non-browser runs (→ consider Option B).
- An MCP server is built (→ consider extracting `webscraper_core` per Option C).

## Alternatives rejected

- **Option B** rejected: unjustified complexity until Playwright stability is a measured problem.
- **Option C** rejected for v0.1: adds a package boundary that's not yet needed. Can be adopted incrementally by extracting modules without breaking the CLI contract.
```

- [ ] **Step 2: Update ARCH.md acceptance checklist**

Change the last line of `docs/ARCH.md § 12` from:
```
- [ ] ADR summary written — follow-up: `docs/ADR/ADR-001-tiered-fetcher.md` capturing the Option A choice
```
to:
```
- [x] ADR summary written — `docs/ADR/ADR-001-tiered-fetcher.md`
```

- [ ] **Step 3: Commit**

```bash
git add docs/ADR/ADR-001-tiered-fetcher.md docs/ARCH.md
git commit -m "docs: ADR-001 captures tiered-fetcher (Option A) decision"
```

---

## Task 25: README smoke validation

**Files:** (no file changes — this verifies the README's shipped commands work)

- [ ] **Step 1: Walk each README example**

For each command in the "Quick start" section of `README.md`, run it against the fixture server (manually replace `https://example.com` with a local fixture URL):

```bash
uv run webscraper fetch http://127.0.0.1:<port>/static/article        # public page, JSON envelope
uv run webscraper fetch http://127.0.0.1:<port>/spa/app                # auto-escalation to Tier 2
uv run webscraper fetch http://127.0.0.1:<port>/static/article --render=markdown
uv run webscraper fetch http://127.0.0.1:<port>/static/article --render=html
uv run webscraper fetch http://127.0.0.1:<port>/static/article --tier=fast
uv run webscraper fetch http://127.0.0.1:<port>/static/article --out /tmp/result.json
uv run webscraper doctor
```

Start the fixture server in a separate terminal with:
```bash
uv run python -c "import uvicorn; from tests.fixtures.server import create_app; uvicorn.run(create_app(), host='127.0.0.1', port=8765)"
```

Expected: every command exits 0 (`doctor` may exit 4 if Chrome/Playwright isn't fully set up on the host — note the gap and move on).

- [ ] **Step 2: If a README example doesn't match actual behavior, fix the README**

Example mismatches to watch for: flag names, exit codes, JSON field names, envelope shape.

- [ ] **Step 3: Commit any README edits**

```bash
git add README.md
git commit -m "docs: align README examples with implemented CLI"
```

(Skip if no drift.)

---

## Task 26: Final verify and tag v0.1

**Files:** (no file changes — release marker)

- [ ] **Step 1: Final verify**

Run: `./scripts/verify.sh`
Expected: green.

- [ ] **Step 2: Confirm F-REQ coverage**

Run: `./scripts/check-functional-coverage.sh`
Expected: 0 uncovered, 0 orphans, 0 untagged.

- [ ] **Step 3: Tag the release**

```bash
git tag -a v0.1.0 -m "webscraper v0.1 — Tiers 1-2, envelope, renderers, doctor"
```

- [ ] **Step 4: Announce**

Let the user know: v0.1 shipped, green verify, tagged. Roadmap for v0.2 (crawl + --download-images), v0.3 (Firecrawl), v0.4 (optional MCP) remains per `docs/PRD.md § Timeline`.

---

## Notes for executors

- **TDD discipline.** Every non-trivial task writes the failing test first, sees it fail, then implements the minimal code to pass. If a test passes before you implement, you didn't write a real test — rework the test.
- **Commit cadence.** One commit per task (sometimes one per logical step within a task). Small commits make review and rollback trivial.
- **Do not amend past commits.** If a hook fails, fix in place and create a new commit; never `--amend`.
- **Do not skip `verify.sh`.** It's the definition of done per `AGENTS.md` invariant #8.
- **Lazy imports for Playwright.** `BrowserFetcher` and `doctor` should import `playwright.sync_api` only inside functions, not at module top level — keeps Tier 1 runs lean.
- **Parallelism.** Tasks 8–12 (parsers) are independent and can be done in parallel by separate subagents. Tasks 15+ depend on 6, 8–13, 14.
- **Don't touch unchanged files.** `AGENTS.md`, `Architecture_Guardrails.md`, `TEST-STRATEGY.md`, `CLAUDE.md` (already updated in the design phase) should not be modified during implementation unless a specific task calls for it.

---

*See `docs/PRD.md` for requirements and `docs/ARCH.md` for architecture. This plan is the authoritative task list for v0.1 implementation.*
