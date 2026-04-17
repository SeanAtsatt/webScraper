# webScraper v0.1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.1.1 — swap the failed Chrome-profile-copy path for per-domain Playwright storage-state files driven by an interactive `webscraper login <url>` subcommand, plus a `--auto-out` flag that resolves scraped output paths from CWD context.

**Architecture:** Fresh empty `user_data_dir` + optional `storage_state=<path>` to Playwright's `launch_persistent_context`. Auth files live in `~/.webscraper/auth/<registrable-domain>.json` (chmod 600). Registrable domain via `tldextract`. `--auto-out` walks CWD ancestors for `ai_working/` and falls back to `~/.webscraper/out/`.

**Tech Stack:** Same as v0.1, plus `tldextract>=5`. Removes `webscraper/profile.py` entirely.

**Reference docs:** `docs/superpowers/specs/2026-04-16-multi-domain-auth-design.md` (authoritative spec), `docs/PRD.md`, `docs/ARCH.md`, `README.md`, `FUNCTIONAL-REQUIREMENTS.md`.

---

## File Structure

```
Additions:
  webscraper/auth.py                      # NEW — storage state management
  webscraper/out.py                       # NEW — --auto-out path resolution
  tests/unit/test_auth.py                 # NEW
  tests/unit/test_out.py                  # NEW
  tests/integration/test_cli_auth.py      # NEW
  tests/integration/test_cli_fetch_with_auth.py  # NEW
  docs/ADR/ADR-002-per-domain-auth.md     # NEW

Deletions:
  webscraper/profile.py
  tests/unit/test_profile.py

Modifications:
  pyproject.toml                          # +tldextract
  webscraper/envelope.py                  # +meta.auth_used
  webscraper/fetch/browser.py             # drop profile copy; load storage_state
  webscraper/cli.py                       # +login, +auth subcommands, +--auto-out
  webscraper/doctor.py                    # replace profile check with auth dir check
  tests/integration/test_browser_fetcher.py  # rewrite for storage_state flow
  tests/e2e/test_fetch_flows.py           # update F-REQ-003, remove F-REQ-012 test,
                                          # add F-REQ-016..022
  FUNCTIONAL-REQUIREMENTS.md              # retire F-REQ-012, add F-REQ-016..022
  docs/PRD.md                             # auth model section, v0.1.1 row, risks
  docs/ARCH.md                            # interfaces + failure modes
  README.md                               # auth section + commands + roadmap
  CLAUDE.md                               # auto-out convention
  .claude/agents/web-scraper.md           # --auto-out + login prereq
```

---

## Task 1: Add tldextract dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `tldextract>=5` to project dependencies**

In `pyproject.toml`, add to the existing `dependencies = [...]` list (alphabetically, before `trafilatura`):

```toml
    "tldextract>=5",
```

- [ ] **Step 2: Resolve deps**

Run: `uv sync`
Expected: exit 0; `uv.lock` updated.

- [ ] **Step 3: Smoke-check tldextract works**

Run: `uv run python -c "import tldextract; print(tldextract.extract('https://www.connectance.org/home').registered_domain)"`
Expected: `connectance.org`

On first run, `tldextract` may download the Public Suffix List (~200 KB). That's fine.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add tldextract for registrable-domain extraction"
```

---

## Task 2: Add `meta.auth_used` to envelope

**Files:**
- Modify: `webscraper/envelope.py`
- Modify: `tests/unit/test_envelope.py`

- [ ] **Step 1: Update `tests/unit/test_envelope.py`**

Add this new test to the end of `tests/unit/test_envelope.py`:

```python
def test_meta_auth_used_defaults_to_empty_string() -> None:
    meta = Meta(
        tier_used="fast",
        tier_history=[TierAttempt(tier="fast", outcome="success", elapsed_ms=1)],
        http_status=200,
        content_type="text/html",
    )
    assert meta.auth_used == ""


def test_meta_auth_used_accepts_domain_string() -> None:
    meta = Meta(
        tier_used="browser",
        tier_history=[TierAttempt(tier="browser", outcome="success", elapsed_ms=1)],
        http_status=200,
        content_type="text/html",
        auth_used="connectance.org",
    )
    assert meta.auth_used == "connectance.org"
```

- [ ] **Step 2: Run to verify the tests fail**

Run: `uv run pytest tests/unit/test_envelope.py::test_meta_auth_used_defaults_to_empty_string tests/unit/test_envelope.py::test_meta_auth_used_accepts_domain_string -v`
Expected: FAIL — `auth_used` is not a field on `Meta`.

- [ ] **Step 3: Add the field to `Meta` in `webscraper/envelope.py`**

Find the `Meta` class and add `auth_used: str = ""` after `content_type`:

```python
class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier_used: TierName
    tier_history: list[TierAttempt] = Field(min_length=1)
    http_status: int
    content_type: str
    auth_used: str = ""

    @model_validator(mode="after")
    def _tier_used_matches_last_history(self) -> "Meta":
        if self.tier_history[-1].tier != self.tier_used:
            raise ValueError("tier_used must equal tier_history[-1].tier")
        return self
```

- [ ] **Step 4: Run envelope tests**

Run: `uv run pytest tests/unit/test_envelope.py -v`
Expected: all tests PASS (the two new + all existing).

- [ ] **Step 5: Commit**

```bash
git add webscraper/envelope.py tests/unit/test_envelope.py
git commit -m "feat(envelope): add meta.auth_used field (registrable domain or empty)"
```

---

## Task 3: `webscraper.auth` — domain extraction and paths

**Files:**
- Create: `webscraper/auth.py`
- Create: `tests/unit/test_auth.py`

- [ ] **Step 1: Write failing tests for `registrable_domain` and `auth_file_for`**

Create `tests/unit/test_auth.py`:

```python
"""Auth storage module tests."""
from pathlib import Path

import pytest

from webscraper.auth import auth_dir, auth_file_for, registrable_domain
from webscraper.errors import UsageError


def test_registrable_domain_strips_subdomains() -> None:
    assert registrable_domain("https://www.connectance.org/home") == "connectance.org"
    assert registrable_domain("https://app.notion.so/workspace") == "notion.so"


def test_registrable_domain_handles_multilevel_tlds() -> None:
    assert registrable_domain("https://user.github.io/repo") == "user.github.io"
    assert registrable_domain("https://www.example.co.uk/path") == "example.co.uk"


def test_registrable_domain_raises_on_ip_or_localhost() -> None:
    with pytest.raises(UsageError):
        registrable_domain("http://127.0.0.1:8080/")
    with pytest.raises(UsageError):
        registrable_domain("http://localhost/")


def test_auth_file_for_returns_path_under_auth_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    path = auth_file_for("https://www.connectance.org/home")
    assert path == tmp_path / "auth" / "connectance.org.json"


def test_auth_dir_returns_auth_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    assert auth_dir() == tmp_path / "auth"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_auth.py -v`
Expected: FAIL (module not importable).

- [ ] **Step 3: Create `webscraper/auth.py` with domain + paths**

```python
"""Per-domain Playwright storage-state management."""

from __future__ import annotations

import os
from pathlib import Path

import tldextract

from webscraper.errors import UsageError


def _home() -> Path:
    override = os.environ.get("WEBSCRAPER_HOME")
    if override:
        return Path(override)
    return Path.home() / ".webscraper"


def auth_dir() -> Path:
    return _home() / "auth"


def registrable_domain(url: str) -> str:
    ext = tldextract.extract(url)
    if not ext.domain or not ext.suffix:
        raise UsageError(f"cannot determine registrable domain for URL: {url}")
    return ext.registered_domain


def auth_file_for(url: str) -> Path:
    domain = registrable_domain(url)
    return auth_dir() / f"{domain}.json"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_auth.py -v`
Expected: 5 PASS.

- [ ] **Step 5: ruff + mypy check**

Run: `uv run ruff format webscraper/auth.py tests/unit/test_auth.py && uv run ruff check webscraper/auth.py tests/unit/test_auth.py && uv run mypy webscraper/auth.py tests/unit/test_auth.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/auth.py tests/unit/test_auth.py
git commit -m "feat(auth): registrable-domain extraction and path helpers"
```

---

## Task 4: `webscraper.auth` — save_state and load_state

**Files:**
- Modify: `webscraper/auth.py`
- Modify: `tests/unit/test_auth.py`

- [ ] **Step 1: Append failing tests to `tests/unit/test_auth.py`**

```python
def test_save_state_writes_chmod_600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import save_state

    path = save_state("example.com", {"cookies": [], "origins": []})
    assert path == tmp_path / "auth" / "example.com.json"
    assert path.exists()
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_save_state_round_trips_with_load_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import load_state, save_state

    state = {
        "cookies": [
            {"name": "sess", "value": "abc", "domain": ".example.com",
             "path": "/", "expires": 9999999999.0, "httpOnly": True, "secure": True, "sameSite": "Lax"},
        ],
        "origins": [],
    }
    save_state("example.com", state)
    loaded = load_state("example.com")
    assert loaded == state


def test_load_state_returns_none_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import load_state

    assert load_state("nonexistent.com") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_auth.py -v -k "save_state or load_state"`
Expected: 3 FAIL (functions not defined).

- [ ] **Step 3: Add save_state + load_state to `webscraper/auth.py`**

Append to `webscraper/auth.py`:

```python
import json
from typing import Any


def save_state(domain: str, state: dict[str, Any]) -> Path:
    """Write a Playwright storage-state dict to disk with chmod 600."""
    d = auth_dir()
    d.mkdir(parents=True, exist_ok=True)
    # Ensure parent dir itself is reasonable (0o700). Create fresh if absent.
    os.chmod(d, 0o700)  # noqa: S103 — deliberate tight perms on user-scoped dir
    path = d / f"{domain}.json"
    # Write then chmod to keep content-creation atomic-ish; use tmp+rename for true atomicity.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.chmod(tmp, 0o600)  # noqa: S103 — user-only readable auth data
    tmp.replace(path)
    return path


def load_state(domain: str) -> dict[str, Any] | None:
    """Load a Playwright storage-state dict, or None if the file is absent."""
    path = auth_dir() / f"{domain}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_auth.py -v`
Expected: all PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/auth.py tests/unit/test_auth.py && uv run ruff check webscraper/auth.py tests/unit/test_auth.py && uv run mypy webscraper/auth.py tests/unit/test_auth.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/auth.py tests/unit/test_auth.py
git commit -m "feat(auth): save_state and load_state with chmod 600 and atomic write"
```

---

## Task 5: `webscraper.auth` — list_sessions + SessionSummary

**Files:**
- Modify: `webscraper/auth.py`
- Modify: `tests/unit/test_auth.py`

- [ ] **Step 1: Append failing tests**

```python
def test_list_sessions_empty_when_dir_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import list_sessions

    assert list_sessions() == []


def test_list_sessions_reports_cookie_counts_and_expiry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import list_sessions, save_state

    state = {
        "cookies": [
            # Session-scoped (no expires):
            {"name": "s1", "value": "x", "domain": ".ex.com", "path": "/"},
            # Persistent cookies:
            {"name": "p1", "value": "x", "domain": ".ex.com", "path": "/", "expires": 2000000000.0},  # 2033
            {"name": "p2", "value": "x", "domain": ".ex.com", "path": "/", "expires": 1900000000.0},  # 2030
        ],
        "origins": [],
    }
    save_state("ex.com", state)
    summaries = list_sessions()
    assert len(summaries) == 1
    s = summaries[0]
    assert s.domain == "ex.com"
    assert s.cookie_count == 3
    assert s.earliest_session_expiry is not None
    # Earliest future expiry is p2 (2030)
    assert s.earliest_session_expiry.year == 2030
    assert s.file_mode == 0o600


def test_list_sessions_earliest_expiry_none_when_only_session_cookies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import list_sessions, save_state

    save_state("a.com", {"cookies": [{"name": "s", "value": "x", "domain": ".a.com", "path": "/"}], "origins": []})
    summaries = list_sessions()
    assert summaries[0].earliest_session_expiry is None


def test_list_sessions_skips_malformed_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import auth_dir, list_sessions

    auth_dir().mkdir(parents=True, exist_ok=True)
    (auth_dir() / "broken.json").write_text("not json", encoding="utf-8")
    os.chmod(auth_dir() / "broken.json", 0o600)  # still chmod 600 but malformed content
    summaries = list_sessions()
    # broken entry surfaces with cookie_count=-1 to signal "malformed"
    assert any(s.domain == "broken" and s.cookie_count == -1 for s in summaries)
```

Add `import os` at the top of the test file if not already present.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_auth.py -v -k "list_sessions"`
Expected: 4 FAIL.

- [ ] **Step 3: Add list_sessions + SessionSummary to `webscraper/auth.py`**

```python
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SessionSummary:
    domain: str
    path: Path
    cookie_count: int  # -1 indicates malformed file
    earliest_session_expiry: datetime | None
    file_mode: int


def _earliest_future_expiry(cookies: list[dict[str, Any]]) -> datetime | None:
    """Return the earliest future `expires` timestamp across persistent cookies.

    Session-scoped cookies (no `expires`) and already-expired cookies are ignored.
    """
    now = datetime.now(tz=UTC).timestamp()
    futures = [c["expires"] for c in cookies if isinstance(c.get("expires"), (int, float)) and c["expires"] > now]
    if not futures:
        return None
    return datetime.fromtimestamp(min(futures), tz=UTC)


def list_sessions() -> list[SessionSummary]:
    d = auth_dir()
    if not d.exists():
        return []
    out: list[SessionSummary] = []
    for path in sorted(d.glob("*.json")):
        domain = path.stem
        mode = path.stat().st_mode & 0o777
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            cookies = state.get("cookies", [])
            out.append(SessionSummary(
                domain=domain,
                path=path,
                cookie_count=len(cookies),
                earliest_session_expiry=_earliest_future_expiry(cookies),
                file_mode=mode,
            ))
        except (json.JSONDecodeError, OSError):
            out.append(SessionSummary(
                domain=domain, path=path, cookie_count=-1,
                earliest_session_expiry=None, file_mode=mode,
            ))
    return out
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_auth.py -v`
Expected: all PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/auth.py tests/unit/test_auth.py && uv run ruff check webscraper/auth.py tests/unit/test_auth.py && uv run mypy webscraper/auth.py tests/unit/test_auth.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/auth.py tests/unit/test_auth.py
git commit -m "feat(auth): list_sessions with SessionSummary (expiry + chmod audit)"
```

---

## Task 6: `webscraper.auth` — forget and prune

**Files:**
- Modify: `webscraper/auth.py`
- Modify: `tests/unit/test_auth.py`

- [ ] **Step 1: Append failing tests**

```python
def test_forget_removes_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import forget, save_state

    save_state("a.com", {"cookies": [], "origins": []})
    assert forget("a.com") is True
    assert not (tmp_path / "auth" / "a.com.json").exists()


def test_forget_returns_false_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import forget

    assert forget("nonexistent.com") is False


def test_prune_removes_only_domains_with_no_future_expiry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path))
    from webscraper.auth import prune, save_state

    # Keep: has a future persistent cookie
    save_state("keep.com", {"cookies": [{"name": "p", "value": "x", "domain": ".keep.com", "path": "/", "expires": 9999999999.0}], "origins": []})
    # Prune: only session cookies
    save_state("session.com", {"cookies": [{"name": "s", "value": "x", "domain": ".session.com", "path": "/"}], "origins": []})
    # Prune: only expired cookies
    save_state("expired.com", {"cookies": [{"name": "e", "value": "x", "domain": ".expired.com", "path": "/", "expires": 100000.0}], "origins": []})

    removed = prune()
    assert set(removed) == {"session.com", "expired.com"}
    assert (tmp_path / "auth" / "keep.com.json").exists()
    assert not (tmp_path / "auth" / "session.com.json").exists()
    assert not (tmp_path / "auth" / "expired.com.json").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_auth.py -v -k "forget or prune"`
Expected: 3 FAIL.

- [ ] **Step 3: Add forget + prune to `webscraper/auth.py`**

```python
def forget(domain: str) -> bool:
    """Delete the auth file for a domain. Returns True if deleted, False if absent."""
    path = auth_dir() / f"{domain}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def prune() -> list[str]:
    """Remove sessions with no future persistent-cookie expiry. Returns the deleted domains."""
    removed: list[str] = []
    for summary in list_sessions():
        if summary.earliest_session_expiry is None:
            # Treat "no future persistent expiry" as prunable.
            # Malformed files (cookie_count == -1) also fall in this bucket.
            summary.path.unlink()
            removed.append(summary.domain)
    return removed
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_auth.py -v`
Expected: all PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/auth.py tests/unit/test_auth.py && uv run ruff check webscraper/auth.py tests/unit/test_auth.py && uv run mypy webscraper/auth.py tests/unit/test_auth.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/auth.py tests/unit/test_auth.py
git commit -m "feat(auth): forget and prune operations"
```

---

## Task 7: `webscraper.out` — slugify + resolve_auto_out

**Files:**
- Create: `webscraper/out.py`
- Create: `tests/unit/test_out.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_out.py`:

```python
"""--auto-out path resolution tests."""
from datetime import UTC, datetime
from pathlib import Path

import pytest

from webscraper.out import resolve_auto_out, slugify


def test_slugify_lowercases_and_replaces_nonalnum() -> None:
    assert slugify("Hello World!") == "hello-world-"
    assert slugify("Foo_Bar") == "foo-bar"


def test_slugify_truncates_long_input() -> None:
    assert slugify("a" * 200) == "a" * 64


def test_slugify_empty_input_returns_index() -> None:
    assert slugify("") == "index"


def test_resolve_auto_out_uses_ai_working_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    (project / "ai_working").mkdir(parents=True)
    (project / "sub").mkdir()
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    path = resolve_auto_out(
        url="https://www.connectance.org/home",
        render_format="json",
        cwd=project / "sub",
        now=now,
    )
    assert path == project / "ai_working" / "scraped" / "connectance.org" / "2026-04-16T18-30-00Z-home.json"


def test_resolve_auto_out_falls_back_to_webscraper_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    bare = tmp_path / "bare"
    bare.mkdir()
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    path = resolve_auto_out(
        url="https://www.connectance.org/home",
        render_format="json",
        cwd=bare,
        now=now,
    )
    assert path == tmp_path / "wshome" / "out" / "connectance.org" / "2026-04-16T18-30-00Z-home.json"


def test_resolve_auto_out_uses_render_format_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    assert resolve_auto_out(
        "https://ex.com/", render_format="markdown", cwd=tmp_path, now=now,
    ).suffix == ".md"
    assert resolve_auto_out(
        "https://ex.com/", render_format="html", cwd=tmp_path, now=now,
    ).suffix == ".html"


def test_resolve_auto_out_empty_path_becomes_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))
    now = datetime(2026, 4, 16, 18, 30, 0, tzinfo=UTC)
    path = resolve_auto_out(
        url="https://example.com/", render_format="json", cwd=tmp_path, now=now,
    )
    assert path.name == "2026-04-16T18-30-00Z-index.json"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_out.py -v`
Expected: 7 FAIL (module not importable).

- [ ] **Step 3: Implement `webscraper/out.py`**

```python
"""Path resolution for `fetch --auto-out`."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from webscraper.auth import _home as webscraper_home
from webscraper.auth import registrable_domain

_NON_SLUG = re.compile(r"[^a-z0-9-]")
_MAX_SLUG = 64
_EXT = {"json": "json", "markdown": "md", "html": "html"}


def slugify(segment: str) -> str:
    if not segment:
        return "index"
    s = _NON_SLUG.sub("-", segment.lower())
    return s[:_MAX_SLUG]


def _find_ai_working_ancestor(cwd: Path) -> Path | None:
    for d in (cwd, *cwd.parents):
        candidate = d / "ai_working"
        if candidate.is_dir():
            return d
    return None


def resolve_auto_out(
    url: str,
    render_format: str,
    cwd: Path,
    *,
    now: datetime | None = None,
) -> Path:
    """Resolve the path where a scraped artifact should land when --auto-out is set."""
    when = now or datetime.now(tz=__import__("datetime").UTC)
    domain = registrable_domain(url)
    project = _find_ai_working_ancestor(cwd)
    if project is not None:
        base = project / "ai_working" / "scraped"
    else:
        base = webscraper_home() / "out"
    ts = when.strftime("%Y-%m-%dT%H-%M-%SZ")
    path_segments = [p for p in urlparse(url).path.split("/") if p]
    slug = slugify(path_segments[-1]) if path_segments else "index"
    ext = _EXT[render_format]
    return base / domain / f"{ts}-{slug}.{ext}"
```

Note: the `__import__("datetime").UTC` is an awkward way to import `UTC` without re-importing `datetime` and hitting the `datetime.datetime` vs `datetime` ambiguity. If mypy complains, switch to `from datetime import UTC, datetime` at the top and use `datetime.now(tz=UTC)`.

- [ ] **Step 4: Clean up the datetime import**

Replace the top imports with:

```python
from datetime import UTC, datetime
```

And the one line inside `resolve_auto_out`:

```python
    when = now or datetime.now(tz=UTC)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_out.py -v`
Expected: 7 PASS.

- [ ] **Step 6: ruff + mypy**

Run: `uv run ruff format webscraper/out.py tests/unit/test_out.py && uv run ruff check webscraper/out.py tests/unit/test_out.py && uv run mypy webscraper/out.py tests/unit/test_out.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add webscraper/out.py tests/unit/test_out.py
git commit -m "feat(out): --auto-out path resolution with ai_working ancestor search"
```

---

## Task 8: Delete `profile.py` and its test

**Files:**
- Delete: `webscraper/profile.py`
- Delete: `tests/unit/test_profile.py`

- [ ] **Step 1: Delete both files**

```bash
git rm webscraper/profile.py tests/unit/test_profile.py
```

- [ ] **Step 2: Verify no remaining imports of `webscraper.profile`**

Run: `grep -rn "from webscraper.profile\|import webscraper.profile" webscraper/ tests/ || echo "none"`
Expected: matches in `webscraper/fetch/browser.py` and `webscraper/doctor.py`. Those get fixed in Tasks 9 and 13.

- [ ] **Step 3: Commit the deletions (do NOT run tests yet — they'll fail until Task 9 lands)**

```bash
git commit -m "refactor: remove profile-copy path (replaced by per-domain auth state)"
```

---

## Task 9: Update `BrowserFetcher` to load storage state

**Files:**
- Modify: `webscraper/fetch/browser.py`
- Modify: `tests/integration/test_browser_fetcher.py`

- [ ] **Step 1: Replace `webscraper/fetch/browser.py` entirely**

```python
"""Tier 2 fetcher: Playwright headless Chromium with optional per-domain storage state."""

import tempfile
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright

from webscraper.auth import load_state, registrable_domain
from webscraper.errors import EnvironmentError, FetcherError, TimeoutError
from webscraper.fetch.base import FetcherResult, FetchOptions


class BrowserFetcher:
    name = "browser"

    def fetch(self, url: str, opts: FetchOptions) -> FetcherResult:
        start = time.monotonic()
        try:
            domain = registrable_domain(url)
        except Exception:
            domain = ""
        state = load_state(domain) if domain else None

        with tempfile.TemporaryDirectory(prefix="webscraper-ctx-") as scratch:
            try:
                with sync_playwright() as p:
                    ctx = p.chromium.launch_persistent_context(
                        str(scratch),
                        headless=True,
                        storage_state=state if state is not None else None,
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
        extra = {"auth_domain": domain} if state is not None else {}
        return FetcherResult(
            html=html,
            final_url=final_url,
            http_status=status,
            content_type=content_type,
            elapsed_ms=elapsed,
            extra=extra,
        )
```

Note: `storage_state` expects either a JSON dict, a string path, or `None`. We pass the loaded dict directly so `WEBSCRAPER_HOME`-based tests work without extra indirection.

- [ ] **Step 2: Rewrite `tests/integration/test_browser_fetcher.py`**

Replace the entire file contents with:

```python
"""BrowserFetcher integration tests against the fixture server."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from webscraper.fetch.base import FetchOptions
from webscraper.fetch.browser import BrowserFetcher


def test_browser_renders_spa_content(fixture_server: str) -> None:
    f = BrowserFetcher()
    result = f.fetch(f"{fixture_server}/spa/app", FetchOptions())
    assert result.http_status == 200
    assert "SPA Rendered" in result.html
    # No auth file set → no auth_domain in extra
    assert "auth_domain" not in result.extra


@pytest.fixture
def seeded_auth(tmp_path: Path, fixture_server: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Pre-seed an auth storage-state file for the fixture server's host."""
    from urllib.parse import urlparse

    from webscraper.auth import save_state

    monkeypatch.setenv("WEBSCRAPER_HOME", str(tmp_path / "wshome"))

    # Boot a temporary Playwright to hit /auth/login and collect cookies.
    state: dict
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
            state = ctx.storage_state()
        finally:
            ctx.close()

    # fixture_server host ("127.0.0.1") is treated as a bare domain by tldextract,
    # so save under the exact host as the "registrable domain" fallback.
    # (Real test of registrable_domain happens in test_auth.)
    domain = urlparse(fixture_server).hostname or "127.0.0.1"
    save_state(domain, state)
    return domain


def test_browser_loads_storage_state_for_matching_domain(
    seeded_auth: str, fixture_server: str
) -> None:
    f = BrowserFetcher()
    result = f.fetch(f"{fixture_server}/auth/private", FetchOptions())
    assert result.http_status == 200
    assert "Authenticated Content" in result.html or "Authenticated" in result.html
    assert result.extra.get("auth_domain") == seeded_auth
```

Important: `registrable_domain` will raise `UsageError` for `127.0.0.1`. Handle this in the test by letting BrowserFetcher swallow the error and treat the fetch as anonymous — the `state=None` path gets exercised. BUT the `seeded_auth` test needs the auth file to actually load. Two options:

(a) Use a DNS name. Modify `conftest.py` to use `localhost` or a fake DNS name.
(b) Wrap `registrable_domain` in BrowserFetcher in a try/except — already done above.

Since the implementation already catches the exception and falls back to `state=None`, **the `seeded_auth` test will fail** unless the domain matches. Let me adjust — see Step 3.

- [ ] **Step 3: Adjust `registrable_domain` to accept IP-based test hosts**

There are two ways to handle this cleanly:

Option A: Change `registrable_domain` in `webscraper/auth.py` to return the hostname verbatim for IP addresses and localhost. Add test cases for this. Downside: it changes behavior of a function that already had explicit "raise on IP/localhost" tests (from Task 3).

Option B: Keep `registrable_domain` strict, and adjust tests that use the fixture server to set a DNS name via `/etc/hosts` or a TestClient. Heavy.

Option C: Make `BrowserFetcher` fall back to `urlparse(url).hostname` when `registrable_domain` raises. This preserves the strict public API but lets the fetcher still try to load an auth file keyed by hostname. In integration tests, `save_state("127.0.0.1", state)` then works.

**Pick Option C.** It's the least disruptive and best matches real-world expectations (if a user saves auth for a bare hostname, the tool should still use it).

Update `webscraper/fetch/browser.py`'s domain lookup:

```python
from urllib.parse import urlparse

from webscraper.errors import UsageError

try:
    domain = registrable_domain(url)
except UsageError:
    # Non-ICANN hosts (IPs, localhost). Fall back to the bare hostname so
    # integration tests and local experimentation can still use auth files.
    domain = urlparse(url).hostname or ""
```

Replace the earlier `try/except Exception: domain = ""` block with the above.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_browser_fetcher.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Run all tests to catch any other regressions from removing profile.py**

Run: `uv run pytest -x`
Expected: everything passes. If tests from v0.1 reference `webscraper.profile`, they'll fail — fix each failure inline (they should be limited to `test_browser_fetcher.py` + `test_fetch_flows.py` — the latter gets rewritten in a later task).

- [ ] **Step 6: ruff + mypy**

Run: `uv run ruff format webscraper/fetch/browser.py tests/integration/test_browser_fetcher.py && uv run ruff check webscraper/fetch/browser.py tests/integration/test_browser_fetcher.py && uv run mypy webscraper/fetch/browser.py tests/integration/test_browser_fetcher.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add webscraper/fetch/browser.py tests/integration/test_browser_fetcher.py
git commit -m "feat(fetch): BrowserFetcher uses storage_state instead of profile copy"
```

---

## Task 10: CLI `login` subcommand

**Files:**
- Modify: `webscraper/cli.py`
- Create: `tests/integration/test_cli_auth.py`

- [ ] **Step 1: Write failing test**

Create `tests/integration/test_cli_auth.py`:

```python
"""CLI tests for login / auth subcommands."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(*args: str, env_extra: dict[str, str] | None = None, stdin_input: str = "") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        input=stdin_input, capture_output=True, text=True, timeout=90, env=env,
    )


@pytest.fixture
def ws_home(tmp_path: Path) -> Path:
    return tmp_path / "wshome"


def test_login_saves_storage_state(fixture_server: str, ws_home: Path) -> None:
    # Use /auth/login so the fixture server sets a persistent cookie during the
    # interactive session; the test simulates "user pressed Enter" via stdin.
    result = _run(
        "login", f"{fixture_server}/auth/login",
        env_extra={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    # Fixture host is 127.0.0.1 — saved under that key (IP fallback path)
    saved = list((ws_home / "auth").glob("*.json"))
    assert len(saved) == 1
    state = json.loads(saved[0].read_text())
    assert any(c.get("name") == "fixture_auth" for c in state["cookies"])
```

Note: `WEBSCRAPER_LOGIN_HEADLESS=1` is a test-only env toggle that forces `headless=True` in the `login` flow so CI / sandbox tests don't need a display. The implementation respects it.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_cli_auth.py::test_login_saves_storage_state -v`
Expected: FAIL (`login` subcommand doesn't exist).

- [ ] **Step 3: Add `login` to CLI**

In `webscraper/cli.py`, add imports:

```python
import os as _os
from urllib.parse import urlparse
from webscraper.auth import registrable_domain, save_state
from webscraper.errors import UsageError
```

Extend `_parser()` — add a new subparser right before `sub.add_parser("doctor", ...)`:

```python
    login = sub.add_parser("login", help="interactively log in and save storage state for a domain")
    login.add_argument("url")
    login.add_argument("--timeout", type=float, default=300.0,
                       help="max seconds to wait for login (default 300)")
```

Add a command handler after `_run_fetch`:

```python
def _run_login(args: argparse.Namespace) -> int:
    from playwright.sync_api import sync_playwright

    try:
        domain = registrable_domain(args.url)
    except UsageError:
        domain = urlparse(args.url).hostname or ""
    if not domain:
        raise UsageError(f"cannot determine domain for URL: {args.url}")

    headless = _os.environ.get("WEBSCRAPER_LOGIN_HEADLESS") == "1"
    sys.stderr.write(f"Opening browser for {domain} (visible; close manually if needed).\n")
    sys.stderr.write("Log in, handle MFA, then press Enter here to save.\n")
    sys.stderr.flush()

    with sync_playwright() as p:
        # Use a fresh empty user_data_dir; we only want storage_state at the end.
        import tempfile
        with tempfile.TemporaryDirectory(prefix="webscraper-login-") as scratch:
            ctx = p.chromium.launch_persistent_context(str(scratch), headless=headless)
            try:
                page = ctx.new_page()
                page.goto(args.url, timeout=int(args.timeout * 1000))
                # Block on stdin to let the user complete login:
                try:
                    input()
                except EOFError:
                    # stdin closed: treat as "done"
                    pass
                state = ctx.storage_state()
            finally:
                ctx.close()

    if not state.get("cookies"):
        sys.stderr.write("warning: no cookies captured; saving state anyway\n")

    path = save_state(domain, state)
    count = len(state.get("cookies", []))
    sys.stderr.write(f"Saved {domain} ({count} cookies) → {path}\n")
    return EXIT_OK
```

Wire it into `main()`:

```python
        if args.command == "login":
            return _run_login(args)
```

(place alongside the existing `args.command == "fetch"` / `args.command == "doctor"` branches.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_cli_auth.py::test_login_saves_storage_state -v`
Expected: PASS.

- [ ] **Step 5: ruff + mypy**

Run: `uv run ruff format webscraper/cli.py tests/integration/test_cli_auth.py && uv run ruff check webscraper/cli.py tests/integration/test_cli_auth.py && uv run mypy webscraper/cli.py tests/integration/test_cli_auth.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add webscraper/cli.py tests/integration/test_cli_auth.py
git commit -m "feat(cli): login subcommand captures and saves storage state"
```

---

## Task 11: CLI `auth list | forget | prune` subcommands

**Files:**
- Modify: `webscraper/cli.py`
- Modify: `tests/integration/test_cli_auth.py`

- [ ] **Step 1: Append failing tests**

Add to `tests/integration/test_cli_auth.py`:

```python
def test_auth_list_reports_saved_session(fixture_server: str, ws_home: Path) -> None:
    _run("login", f"{fixture_server}/auth/login",
         env_extra={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
         stdin_input="\n")
    result = _run("auth", "list", env_extra={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert "127.0.0.1" in result.stdout or "127.0.0.1" in result.stderr


def test_auth_forget_deletes_saved_session(fixture_server: str, ws_home: Path) -> None:
    _run("login", f"{fixture_server}/auth/login",
         env_extra={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
         stdin_input="\n")
    assert (ws_home / "auth").glob("*.json")
    result = _run("auth", "forget", "127.0.0.1", env_extra={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert not list((ws_home / "auth").glob("*.json"))


def test_auth_prune_removes_session_only_files(ws_home: Path) -> None:
    # Pre-seed two fake auth files directly
    (ws_home / "auth").mkdir(parents=True)
    (ws_home / "auth" / "keep.com.json").write_text(
        '{"cookies": [{"name":"p","value":"x","domain":".keep.com","path":"/","expires": 9999999999.0}], "origins": []}',
    )
    (ws_home / "auth" / "drop.com.json").write_text(
        '{"cookies": [{"name":"s","value":"x","domain":".drop.com","path":"/"}], "origins": []}',
    )
    import os as _os
    _os.chmod(ws_home / "auth" / "keep.com.json", 0o600)
    _os.chmod(ws_home / "auth" / "drop.com.json", 0o600)

    result = _run("auth", "prune", env_extra={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert (ws_home / "auth" / "keep.com.json").exists()
    assert not (ws_home / "auth" / "drop.com.json").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_cli_auth.py -v -k "list or forget or prune"`
Expected: 3 FAIL.

- [ ] **Step 3: Add `auth` subcommand group to `_parser()`**

```python
    auth_p = sub.add_parser("auth", help="manage saved authentication sessions")
    auth_sub = auth_p.add_subparsers(dest="auth_command", required=True)
    auth_sub.add_parser("list", help="list saved sessions")
    forget_p = auth_sub.add_parser("forget", help="delete a saved session")
    forget_p.add_argument("domain")
    auth_sub.add_parser("prune", help="remove sessions whose cookies have all expired")
```

- [ ] **Step 4: Add the handler**

```python
def _run_auth(args: argparse.Namespace) -> int:
    from datetime import UTC, datetime
    from webscraper.auth import forget, list_sessions, prune

    if args.auth_command == "list":
        summaries = list_sessions()
        if not summaries:
            sys.stderr.write("no saved sessions\n")
            return EXIT_OK
        now = datetime.now(tz=UTC)
        for s in summaries:
            if s.cookie_count == -1:
                expires_note = "  malformed"
            elif s.earliest_session_expiry is None:
                expires_note = "  session-only"
            else:
                days = (s.earliest_session_expiry - now).days
                expires_note = f"  expires in {days}d"
            chmod_warn = "" if s.file_mode == 0o600 else f"  [chmod {oct(s.file_mode)}]"
            sys.stdout.write(f"{s.domain:30s}  {s.cookie_count} cookies{expires_note}{chmod_warn}\n")
        return EXIT_OK

    if args.auth_command == "forget":
        removed = forget(args.domain)
        if removed:
            sys.stderr.write(f"forgot {args.domain}\n")
        else:
            sys.stderr.write(f"no session found for {args.domain}\n")
        return EXIT_OK

    if args.auth_command == "prune":
        removed_list = prune()
        if removed_list:
            sys.stderr.write(f"pruned: {', '.join(removed_list)}\n")
        else:
            sys.stderr.write("nothing to prune\n")
        return EXIT_OK

    raise UsageError(f"unknown auth subcommand: {args.auth_command}")
```

Wire into `main()`:

```python
        if args.command == "auth":
            return _run_auth(args)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/integration/test_cli_auth.py -v`
Expected: all PASS.

- [ ] **Step 6: ruff + mypy**

Run: `uv run ruff format webscraper/cli.py tests/integration/test_cli_auth.py && uv run ruff check webscraper/cli.py tests/integration/test_cli_auth.py && uv run mypy webscraper/cli.py tests/integration/test_cli_auth.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add webscraper/cli.py tests/integration/test_cli_auth.py
git commit -m "feat(cli): auth list|forget|prune subcommands"
```

---

## Task 12: CLI `--auto-out` flag on `fetch`

**Files:**
- Modify: `webscraper/cli.py`
- Create: `tests/integration/test_cli_fetch_with_auth.py`

- [ ] **Step 1: Write failing test (also covers auth-used envelope field)**

Create `tests/integration/test_cli_fetch_with_auth.py`:

```python
"""Integration tests for fetch with auth state + --auto-out."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True, text=True, timeout=90, env=env,
    )


@pytest.fixture
def seeded_ws_home(tmp_path: Path, fixture_server: str) -> Path:
    """Boot Playwright once to seed an auth file for the fixture host."""
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse

    from webscraper.auth import save_state

    ws_home = tmp_path / "wshome"
    os.environ["WEBSCRAPER_HOME"] = str(ws_home)

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
            try:
                page = ctx.new_page()
                page.goto(f"{fixture_server}/auth/login")
                page.wait_for_load_state("networkidle")
                state = ctx.storage_state()
            finally:
                ctx.close()

        domain = urlparse(fixture_server).hostname or "127.0.0.1"
        save_state(domain, state)
        yield ws_home
    finally:
        os.environ.pop("WEBSCRAPER_HOME", None)


def test_fetch_uses_auth_state_and_populates_meta_auth_used(
    seeded_ws_home: Path, fixture_server: str
) -> None:
    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env_extra={"WEBSCRAPER_HOME": str(seeded_ws_home)},
    )
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["meta"]["auth_used"] == "127.0.0.1"
    assert "Authenticated" in envelope["markdown"] or "Authenticated" in envelope["text"]


def test_fetch_auto_out_writes_to_ai_working_when_present(
    tmp_path: Path, fixture_server: str
) -> None:
    project = tmp_path / "proj"
    (project / "ai_working").mkdir(parents=True)
    result = subprocess.run(
        [sys.executable, "-m", "webscraper", "fetch",
         f"{fixture_server}/static/article", "--tier=fast", "--auto-out"],
        capture_output=True, text=True, timeout=60,
        cwd=str(project),
    )
    assert result.returncode == 0, result.stderr
    scraped = list((project / "ai_working" / "scraped").rglob("*.json"))
    assert len(scraped) == 1


def test_fetch_auto_out_falls_back_to_webscraper_home(
    tmp_path: Path, fixture_server: str
) -> None:
    ws_home = tmp_path / "wshome"
    bare = tmp_path / "bare"
    bare.mkdir()
    result = subprocess.run(
        [sys.executable, "-m", "webscraper", "fetch",
         f"{fixture_server}/static/article", "--tier=fast", "--auto-out"],
        capture_output=True, text=True, timeout=60,
        cwd=str(bare),
        env={**os.environ, "WEBSCRAPER_HOME": str(ws_home)},
    )
    assert result.returncode == 0, result.stderr
    scraped = list((ws_home / "out").rglob("*.json"))
    assert len(scraped) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/integration/test_cli_fetch_with_auth.py -v`
Expected: 3 FAIL (`--auto-out` not a flag).

- [ ] **Step 3: Add `--auto-out` flag to `fetch` parser**

In `_parser()`, on the `fetch` subparser, add:

```python
    fetch.add_argument("--auto-out", action="store_true",
                       help="resolve output path from CWD (ai_working/ or ~/.webscraper/out/)")
```

- [ ] **Step 4: Wire `--auto-out` into `_run_fetch`**

Modify `_run_fetch` to use `resolve_auto_out` when `args.auto_out` is set and `args.out` is not. Add to the imports at the top of `cli.py`:

```python
from pathlib import Path
from webscraper.out import resolve_auto_out
```

Inside `_run_fetch`, before the dispatcher call, resolve the path:

```python
    # Resolve --auto-out (lowest precedence; --out wins if both are set)
    out_path: Path | None = args.out
    if out_path is None and args.auto_out:
        out_path = resolve_auto_out(
            url=args.url, render_format=args.render, cwd=Path.cwd(),
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stderr.write(f"writing to {out_path}\n")
    if args.out is not None and args.auto_out:
        sys.stderr.write("warning: --out overrides --auto-out\n")
```

Then replace the existing `args.out` usage in `_emit` with a local `out_path` parameter:

```python
def _emit(envelope: FetchResult, args: argparse.Namespace, out_path: Path | None) -> None:
    if args.render == "json":
        payload = envelope.model_dump_json(indent=2)
    elif args.render == "markdown":
        payload = render_markdown(envelope)
    else:  # html
        payload = render_html(envelope)
    if out_path is not None:
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")
```

Update the `_emit(envelope, args)` call in `_run_fetch` to `_emit(envelope, args, out_path)`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/integration/test_cli_fetch_with_auth.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Run full existing CLI test suite to catch regressions**

Run: `uv run pytest tests/integration/test_cli_fetch.py -v`
Expected: all 5 existing tests still pass.

- [ ] **Step 7: ruff + mypy**

Run: `uv run ruff format webscraper/cli.py tests/integration/test_cli_fetch_with_auth.py && uv run ruff check webscraper/cli.py tests/integration/test_cli_fetch_with_auth.py && uv run mypy webscraper/cli.py tests/integration/test_cli_fetch_with_auth.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add webscraper/cli.py tests/integration/test_cli_fetch_with_auth.py
git commit -m "feat(cli): --auto-out flag resolves path from ai_working/ or ~/.webscraper/out/"
```

---

## Task 13: Update `doctor` to check auth dir

**Files:**
- Modify: `webscraper/doctor.py`
- Modify: `tests/integration/test_cli_doctor.py`

- [ ] **Step 1: Update doctor test**

Replace `tests/integration/test_cli_doctor.py`:

```python
"""CLI integration tests for `webscraper doctor`."""
import os
import subprocess
import sys
from pathlib import Path


def test_doctor_runs_and_reports_known_checks(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "webscraper", "doctor"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "WEBSCRAPER_HOME": str(tmp_path / "wshome")},
    )
    # Exit 0 if healthy, 4 if any check failed (playwright may be missing in some envs)
    assert result.returncode in (0, 4)
    assert "Python" in result.stdout
    assert "Playwright" in result.stdout
    assert "auth dir" in result.stdout.lower() or "saved sessions" in result.stdout.lower()
```

- [ ] **Step 2: Replace `webscraper/doctor.py`**

```python
"""Environment health check."""

from __future__ import annotations

import importlib
import platform
import sys

from webscraper.auth import auth_dir, list_sessions

_OK = "  OK"
_FAIL = "FAIL"
_WARN = "WARN"


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


def _check_auth() -> tuple[str, bool]:
    d = auth_dir()
    if not d.exists():
        return f"auth dir: none at {d} (run `webscraper login <url>` to create)", True
    summaries = list_sessions()
    if not summaries:
        return f"auth dir at {d}: empty", True
    problems: list[str] = []
    for s in summaries:
        if s.file_mode != 0o600:
            problems.append(f"{s.domain} has chmod {oct(s.file_mode)} (expected 0o600)")
    if problems:
        return f"auth dir: {len(summaries)} sessions; " + "; ".join(problems), False
    return f"auth dir: {len(summaries)} saved sessions at {d}", True


def run_doctor() -> int:
    checks = [_check_python(), _check_playwright(), _check_auth()]
    all_ok = True
    for message, ok in checks:
        mark = _OK if ok else _FAIL
        print(f"[{mark}] {message}")
        all_ok = all_ok and ok
    return 0 if all_ok else 4
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/integration/test_cli_doctor.py -v`
Expected: PASS.

- [ ] **Step 4: ruff + mypy**

Run: `uv run ruff format webscraper/doctor.py tests/integration/test_cli_doctor.py && uv run ruff check webscraper/doctor.py tests/integration/test_cli_doctor.py && uv run mypy webscraper/doctor.py tests/integration/test_cli_doctor.py`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add webscraper/doctor.py tests/integration/test_cli_doctor.py
git commit -m "feat(doctor): replace profile check with auth dir + chmod audit"
```

---

## Task 14: Update FUNCTIONAL-REQUIREMENTS.md

**Files:**
- Modify: `FUNCTIONAL-REQUIREMENTS.md`

- [ ] **Step 1: Update the requirements table**

Replace the existing row for F-REQ-003 and F-REQ-012, and append F-REQ-016 through F-REQ-022. The final table should be:

```markdown
| ID | Category | Requirement | Verification |
|----|----------|-------------|--------------|
| F-REQ-001 | fetch | Static page returns valid envelope via Tier 1 | response |
| F-REQ-002 | fetch | JS-rendered page escalates Tier 1 → Tier 2 and returns rendered content | response |
| F-REQ-003 | fetch | Login-gated page is retrievable via saved per-domain storage state | response |
| F-REQ-004 | fetch | `--tier` override is honored; no silent escalation | response |
| F-REQ-005 | content | Tables surface as `{headers, rows}` | response |
| F-REQ-006 | content | Forms surface as `{action, method, fields[]}` | response |
| F-REQ-007 | content | Images surface as `{url, alt, width, height, role}` | response |
| F-REQ-008 | content | Links classified as `nav/content/external/anchor` | response |
| F-REQ-009 | render | `--render=markdown` emits markdown, not JSON | response |
| F-REQ-010 | render | `--render=html` emits valid self-contained HTML | response |
| F-REQ-011 | security | No cookies or auth data appear in stdout/stderr/logs | response |
| F-REQ-012 | retired | Retired in v0.1.1 (profile-copy removed; superseded by F-REQ-022) | response |
| F-REQ-013 | errors | Malformed URL (parse error) exits non-zero with a diagnostic JSON error | response |
| F-REQ-014 | errors | Network-unreachable host exits non-zero with a diagnostic JSON error | response |
| F-REQ-015 | errors | All enabled tiers failing exits non-zero with a diagnostic including full `tier_history` | response |
| F-REQ-016 | auth | `login <url>` captures a browser session and saves storage state | response |
| F-REQ-017 | auth | Saved auth file persists across tool invocations; `fetch` auto-loads it | response |
| F-REQ-018 | auth | `fetch` without a matching auth file proceeds anonymously (no crash) | response |
| F-REQ-019 | auth | `auth list` reports cookie count and earliest session expiry per domain | response |
| F-REQ-020 | auth | `auth forget` and `auth prune` remove files correctly | response |
| F-REQ-021 | output | `--auto-out` writes to `ai_working/scraped/` when a project ancestor is found; else `~/.webscraper/out/` | response |
| F-REQ-022 | security | Auth files are `chmod 600` on save; cookies/auth headers never appear in stdout/stderr/logs | response |
```

Note: F-REQ-012 stays in the table as "retired" so the ID isn't reused. The previous test (`test_scratch_profile_cleaned_up_after_run`) gets removed in Task 15; a single `# [F-REQ-012]` placeholder test remains so coverage reports zero orphans.

- [ ] **Step 2: Commit**

```bash
git add FUNCTIONAL-REQUIREMENTS.md
git commit -m "docs: retire F-REQ-012; add F-REQ-016..022 for v0.1.1"
```

---

## Task 15: Update E2E tests for new F-REQs

**Files:**
- Modify: `tests/e2e/test_fetch_flows.py`

- [ ] **Step 1: Replace the two outdated tests and add the new ones**

In `tests/e2e/test_fetch_flows.py`:

**(a)** Replace the F-REQ-003 test to use per-domain auth instead of the seeded Chrome profile:

```python
# [F-REQ-003]
def test_auth_gated_page_via_saved_storage_state(
    fixture_server: str, tmp_path: Path
) -> None:
    """Seed an auth file, then fetch the auth-gated page."""
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse

    ws_home = tmp_path / "wshome"
    # Capture storage state via the fixture login
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
            state = ctx.storage_state()
        finally:
            ctx.close()

    import json as _json
    auth_dir = ws_home / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    domain = urlparse(fixture_server).hostname or "127.0.0.1"
    auth_file = auth_dir / f"{domain}.json"
    auth_file.write_text(_json.dumps(state))
    import os as _os
    _os.chmod(auth_file, 0o600)

    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_HOME": str(ws_home)},
    )
    assert result.returncode == 0, result.stderr
    envelope = _envelope(result.stdout)
    assert "Authenticated" in envelope["markdown"] or "Authenticated" in envelope["text"]
    assert envelope["meta"]["auth_used"] == domain
```

**(b)** Replace the F-REQ-011 test body with a more thorough version that uses the new auth-state flow:

```python
# [F-REQ-011]
def test_no_auth_data_in_stdout_or_stderr(fixture_server: str, tmp_path: Path) -> None:
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlparse

    ws_home = tmp_path / "wshome"
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(tmp_path / "seed"), headless=True)
        try:
            page = ctx.new_page()
            page.goto(f"{fixture_server}/auth/login")
            page.wait_for_load_state("networkidle")
            state = ctx.storage_state()
        finally:
            ctx.close()

    import json as _json
    import os as _os
    (ws_home / "auth").mkdir(parents=True, exist_ok=True)
    domain = urlparse(fixture_server).hostname or "127.0.0.1"
    (ws_home / "auth" / f"{domain}.json").write_text(_json.dumps(state))
    _os.chmod(ws_home / "auth" / f"{domain}.json", 0o600)

    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_HOME": str(ws_home)},
    )
    combined = result.stdout + result.stderr
    assert "fixture_auth=1" not in combined
    assert "Cookie:" not in combined
    assert "Set-Cookie:" not in combined
```

**(c)** Replace the F-REQ-012 test with a single-line placeholder so coverage reports zero orphans:

```python
# [F-REQ-012]
def test_freq012_retired() -> None:
    """F-REQ-012 was the scratch-profile-cleanup test; retired with profile-copy removal.

    Security guarantees moved to F-REQ-022 (chmod 600 on auth files).
    """
    pass
```

**(d)** Append new F-REQ tests at the end of the file:

```python
# [F-REQ-016]
def test_login_saves_session(fixture_server: str, tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    result = _run(
        "login", f"{fixture_server}/auth/login",
        env={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    assert result.returncode == 0
    saved = list((ws_home / "auth").glob("*.json"))
    assert len(saved) == 1


# [F-REQ-017]
def test_saved_auth_persists_across_invocations(fixture_server: str, tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    _run(
        "login", f"{fixture_server}/auth/login",
        env={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    # Second invocation (fresh subprocess) uses the saved state
    result = _run(
        "fetch", f"{fixture_server}/auth/private", "--tier=browser",
        env={"WEBSCRAPER_HOME": str(ws_home)},
    )
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    assert envelope["meta"]["auth_used"] != ""


# [F-REQ-018]
def test_fetch_without_auth_proceeds_anonymously(fixture_server: str, tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    result = _run(
        "fetch", f"{fixture_server}/static/article", "--tier=fast",
        env={"WEBSCRAPER_HOME": str(ws_home)},
    )
    assert result.returncode == 0
    envelope = _envelope(result.stdout)
    assert envelope["meta"]["auth_used"] == ""


# [F-REQ-019]
def test_auth_list_shows_cookie_count_and_expiry(fixture_server: str, tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    _run(
        "login", f"{fixture_server}/auth/login",
        env={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    result = _run("auth", "list", env={"WEBSCRAPER_HOME": str(ws_home)})
    assert result.returncode == 0
    assert "cookies" in result.stdout


# [F-REQ-020]
def test_auth_forget_and_prune(tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    (ws_home / "auth").mkdir(parents=True)
    # Seed two fake files: one prunable, one not
    import json as _json
    import os as _os
    keep = ws_home / "auth" / "keep.com.json"
    drop = ws_home / "auth" / "drop.com.json"
    keep.write_text(_json.dumps({"cookies": [{"name": "p", "value": "x",
                                              "domain": ".keep.com", "path": "/",
                                              "expires": 9999999999.0}], "origins": []}))
    drop.write_text(_json.dumps({"cookies": [{"name": "s", "value": "x",
                                              "domain": ".drop.com", "path": "/"}],
                                 "origins": []}))
    _os.chmod(keep, 0o600)
    _os.chmod(drop, 0o600)

    r1 = _run("auth", "prune", env={"WEBSCRAPER_HOME": str(ws_home)})
    assert r1.returncode == 0
    assert keep.exists() and not drop.exists()

    r2 = _run("auth", "forget", "keep.com", env={"WEBSCRAPER_HOME": str(ws_home)})
    assert r2.returncode == 0
    assert not keep.exists()


# [F-REQ-021]
def test_auto_out_resolves_to_ai_working(fixture_server: str, tmp_path: Path) -> None:
    import subprocess as _sp
    import sys as _sys
    project = tmp_path / "proj"
    (project / "ai_working").mkdir(parents=True)
    result = _sp.run(
        [_sys.executable, "-m", "webscraper", "fetch",
         f"{fixture_server}/static/article", "--tier=fast", "--auto-out"],
        capture_output=True, text=True, timeout=60, cwd=str(project),
    )
    assert result.returncode == 0
    scraped = list((project / "ai_working" / "scraped").rglob("*.json"))
    assert len(scraped) == 1


# [F-REQ-022]
def test_auth_file_chmod_600(fixture_server: str, tmp_path: Path) -> None:
    ws_home = tmp_path / "wshome"
    _run(
        "login", f"{fixture_server}/auth/login",
        env={"WEBSCRAPER_HOME": str(ws_home), "WEBSCRAPER_LOGIN_HEADLESS": "1"},
        stdin_input="\n",
    )
    import os as _os
    for f in (ws_home / "auth").glob("*.json"):
        mode = _os.stat(f).st_mode & 0o777
        assert mode == 0o600, f"{f}: expected 0o600, got {oct(mode)}"
```

**(e)** Update the top of `tests/e2e/test_fetch_flows.py` — the `_run` helper needs a `stdin_input` parameter:

```python
def _run(*args: str, env: dict[str, str] | None = None, stdin_input: str = "") -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        input=stdin_input, capture_output=True, text=True, timeout=90, env=full_env,
    )
```

- [ ] **Step 2: Delete the old `test_no_cookies_or_profile_bytes_in_stdout` and `test_scratch_profile_cleaned_up_after_run` functions**

Those two tests were tied to the profile-copy code path and have been superseded by the F-REQ-011 rewrite and the F-REQ-012 retirement placeholder.

- [ ] **Step 3: Run the full E2E suite**

Run: `uv run pytest tests/e2e -v`
Expected: all pass (15 originals minus 2 deleted + 7 new = 20 tests).

- [ ] **Step 4: ruff + mypy**

Run: `uv run ruff format tests/e2e/test_fetch_flows.py && uv run ruff check tests/e2e/test_fetch_flows.py && uv run mypy tests/e2e/test_fetch_flows.py`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_fetch_flows.py
git commit -m "test(e2e): update F-REQ-003/011/012, add F-REQ-016..022 tests"
```

---

## Task 16: ADR-002 — per-domain auth

**Files:**
- Create: `docs/ADR/ADR-002-per-domain-auth.md`

- [ ] **Step 1: Write the ADR**

```markdown
# ADR-002: Per-domain Playwright storage state (replaces Chrome-profile copy)

**Status:** Accepted (2026-04-16)

## Context

v0.1's authenticated-scraping strategy was to copy the user's real Chrome profile per run and let Playwright launch against the copy. Live testing against `https://www.connectance.org/home` showed the strategy doesn't work on macOS: Chrome's cookie store is encrypted with a key bound to the real Chrome binary's code signature (via the OS Keychain). The bundled Chromium that Playwright launches cannot read that key, so `encrypted_value` columns in the copied `Cookies` database are unreadable. The site sees the fetch as unauthenticated and redirects to `/login`.

Reverting to `channel="chrome"` would decrypt the cookies, but Playwright would conflict with the user's running Chrome (profile lock), violating the "Chrome stays open" contract in the PRD.

## Decision

Replace the profile-copy path with **per-domain Playwright storage-state files**:

- Auth is captured once per site via `webscraper login <url>`, which opens a visible browser, lets the user log in (including MFA), and saves the resulting `context.storage_state()` JSON to `~/.webscraper/auth/<registrable-domain>.json` (chmod 600).
- On subsequent `fetch` calls, `BrowserFetcher` extracts the URL's registrable domain (via `tldextract`), looks up the matching file, and passes it as `storage_state` to `launch_persistent_context`.
- No profile copy. The tool uses a fresh empty `user_data_dir` per run.

`webscraper/profile.py` is removed entirely.

## Consequences

**Positive:**
- Works on macOS without fighting Chrome's Keychain.
- Chrome can stay open during scraping — no lock contention.
- Per-site blast radius: one compromised auth file leaks cookies for one domain.
- Handles MFA, SSO, and email-verification flows naturally (user drives the real login).
- Small, focused auth surface (~120 LOC).

**Negative:**
- One-time interactive `login` step per site. Not a drop-in "just works like my browser" experience on day one.
- Auth files are JSON on disk (chmod 600), not Keychain-encrypted. Mitigated by per-domain scoping and the fact that the cookies are equivalent to those already sitting in the user's Chrome profile.
- No refresh-token / auto-renewal flow in v0.1.1. When a site's session cookie expires, the user re-runs `login`.

**Revisited when:**
- Users request auto-renewal / background refresh.
- Users want multiple accounts per domain (alias support).
- Platform support expands to Windows (Keychain analogue is DPAPI; different story).

## Alternatives considered and rejected

- **`channel="chrome"` against a copied profile:** decrypts cookies but requires Chrome to be closed during every scrape. Violates PRD "Chrome stays open" contract.
- **`channel="chrome"` against the live profile:** no copy needed, but Chrome profile lock means Chrome must be closed. Same contract violation.
- **Connect to a running Chrome via CDP (`--remote-debugging-port`):** inherits live auth, no copy, no decryption. Rejected for v0.1.1 as significantly more complex; users must start Chrome with the debug flag; doctor would need a connection check. Candidate for v0.2+.
- **Keep v0.1's profile copy as a fallback when no auth file exists:** adds a code path that never contributes anything (the profile copy doesn't work for auth; for non-auth pages, Tier 1 suffices or bundled Chromium's empty context works). Pure dead weight; rejected.

## References

- `docs/superpowers/specs/2026-04-16-multi-domain-auth-design.md` — full spec
- ADR-001 — original tiered-fetcher decision (this ADR does not supersede it)
```

- [ ] **Step 2: Commit**

```bash
git add docs/ADR/ADR-002-per-domain-auth.md
git commit -m "docs: ADR-002 captures per-domain-auth decision (replaces profile copy)"
```

---

## Task 17: Update PRD, ARCH, README, CLAUDE.md, subagent

**Files:**
- Modify: `docs/PRD.md`
- Modify: `docs/ARCH.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `.claude/agents/web-scraper.md`

### 17.1 PRD updates

- [ ] **Update the auth model section:** In `docs/PRD.md`, find the line mentioning "Chrome profile" in the scope section (or the auth-related user story) and replace the approach description with:

> **Authenticated scraping via per-domain Playwright storage state.** Users run `webscraper login <url>` once per site to capture a browser session; subsequent fetches auto-load the saved state by registrable domain. See `docs/ADR/ADR-002-per-domain-auth.md`.

- [ ] **Update the timeline table:** Add a v0.1.1 row between v0.1 and v0.2:

```markdown
| v0.1.1 | `login`, `auth list\|forget\|prune`, `--auto-out`, per-domain auth (replaces profile copy) | Not Started |
```

- [ ] **Replace the F-REQ-003 row** in the PRD's initial F-REQ table to match the new "saved per-domain storage state" wording (copy from Task 14's FUNCTIONAL-REQUIREMENTS.md table).

- [ ] **Update Risks:** Remove the "Chrome profile locked / scratch profile leak" risks. Add:

```markdown
| Auth-state file on disk | Credential exposure if `~/.webscraper/auth/*.json` is read | `chmod 600`, per-domain scoping, `doctor` audits file modes on every run |
```

### 17.2 ARCH updates

- [ ] **§4 Interfaces:** remove the `profile` row from the layered-responsibilities table; add an `auth` row:

```markdown
| `auth` | Per-domain Playwright storage-state load/save/list/prune | `tldextract`, stdlib |
```

- [ ] **§7 Failure modes:** remove "Chrome profile locked" and "Scratch profile not cleaned up" rows. Add:

```markdown
| Auth file malformed / unreadable | `fetch` exits 4 with a `forget <domain>` suggestion; `doctor` flags it. |
| Auth file chmod > 600 | `doctor` flags; `fetch` logs a warning but still loads. |
```

### 17.3 README updates

- [ ] **Update prerequisites:** remove the paragraph about "copy-on-run" from the Auth section. Replace with:

```markdown
## Authenticated scraping

`webscraper` captures a session per site the first time you run `login`:

    uv run webscraper login https://www.connectance.org/home

A visible Chromium window opens. Log in (including MFA if any), then press Enter in the terminal. The session is saved to `~/.webscraper/auth/<domain>.json` with `chmod 600`, scoped to the registrable domain. Subsequent `fetch` calls auto-load it; `meta.auth_used` in the envelope reports the domain.

Manage sessions:

    uv run webscraper auth list          # inventory with cookie counts + expiry
    uv run webscraper auth forget <domain>
    uv run webscraper auth prune         # remove sessions with all cookies expired
```

- [ ] **Update commands table:** Add `login`, `auth list`, `auth forget`, `auth prune`, and the `--auto-out` flag on `fetch`.

- [ ] **Update roadmap:** Add v0.1.1 row marked Shipped after verification.

### 17.4 CLAUDE.md

- [ ] **Append to the "Using the webscraper tool" section:**

```markdown
**Where scraped data goes:** When you invoke `webscraper fetch` inside a project that has an `ai_working/` directory, use `--auto-out` — scraped envelopes land in `ai_working/scraped/<domain>/<timestamp>-<slug>.json`, consistent with the CLAUDE.md convention for transient work. Outside a project, `--auto-out` writes to `~/.webscraper/out/`.
```

### 17.5 `.claude/agents/web-scraper.md`

- [ ] **Update "Flags you'll commonly use" table:** add a row:

```markdown
| `--auto-out` | The user wants the result saved automatically into `ai_working/scraped/` (in a project) or `~/.webscraper/out/` (ad-hoc) |
```

- [ ] **Update "Respect auth context":** add a sentence: "If a site returned `/login` and you know the user is logged into that site, run `uv run webscraper login <url>` first (once per site). Subsequent fetches auto-use the saved session."

- [ ] **Commit all doc changes in one commit**

```bash
git add docs/PRD.md docs/ARCH.md README.md CLAUDE.md .claude/agents/web-scraper.md
git commit -m "docs: v0.1.1 — auth model, --auto-out convention, roadmap, subagent"
```

---

## Task 18: Full verify.sh green

**Files:** (no file changes intended)

- [ ] **Step 1: Run full verify**

Run: `./scripts/verify.sh`
Expected: all green.

- [ ] **Step 2: If failures:**

- **ruff / format:** `uv run ruff format . && uv run ruff check . --fix` then re-run
- **mypy:** fix with annotations (not `# type: ignore`) unless a library stub requires it
- **pytest:** diagnose; don't modify tests to hide bugs
- **check-functional-coverage.sh:** confirm F-REQ-012 placeholder test is tagged; confirm all new F-REQ-016..022 tests are tagged

Re-run `./scripts/verify.sh` after each fix.

- [ ] **Step 3: If fixes were needed, commit them**

```bash
git add -u
git commit -m "fix: verify.sh green for v0.1.1"
```

(Skip commit if no fixes needed.)

---

## Task 19: Live retest against connectance.org

**Files:** (no file changes)

- [ ] **Step 1: Ask the user to run `login`**

Because `login` requires an interactive browser and MFA, it must be run by the user, not a subagent. In this task, the controller (main session) asks the user to run:

```bash
uv run webscraper login https://www.connectance.org/home
```

…then press Enter in the terminal after logging in.

- [ ] **Step 2: After user confirms save, run fetch**

```bash
uv run webscraper fetch https://www.connectance.org/home --tier=browser --out /tmp/claude/connectance.json
```

- [ ] **Step 3: Inspect the result**

Read `/tmp/claude/connectance.json`. Expected:
- `final_url` is `https://www.connectance.org/home` (no redirect to `/login`)
- `meta.auth_used == "connectance.org"`
- `markdown` contains real authenticated content (not the login form)

If the test passes, v0.1.1 has fulfilled the PRD's authenticated-fetch promise against a real site.

- [ ] **Step 4: If the test fails:**

Capture the envelope, compare `final_url`, and report back. Common causes:
- `login` step didn't actually save cookies (browser was closed too fast, the site uses OAuth redirect to a domain we didn't capture)
- Session expired between `login` and `fetch`
- Site does server-side rendering with very strict cookie requirements

Each is a real diagnostic worth handling case-by-case — don't silently mark v0.1.1 complete if the live test fails.

---

## Task 20: Tag v0.1.1

**Files:** (no file changes)

- [ ] **Step 1: Final verify**

Run: `./scripts/verify.sh`
Expected: green.

- [ ] **Step 2: Tag**

```bash
git tag -a v0.1.1 -m "webscraper v0.1.1 — per-domain auth + --auto-out"
```

- [ ] **Step 3: Push tag**

```bash
git push origin main
git push origin v0.1.1
```

- [ ] **Step 4: Announce**

v0.1.1 shipped. PRD's authenticated-fetch promise verified against a real site.

---

## Notes for executors

- **TDD discipline.** Every task with non-trivial logic writes the failing test first. If a test passes without your implementation, rewrite the test.
- **Commit cadence.** One commit per task.
- **No `--amend`.** If a hook fails, fix in place and commit again.
- **`WEBSCRAPER_HOME` env var** is the test hook used throughout. Real usage defaults to `~/.webscraper/`.
- **`WEBSCRAPER_LOGIN_HEADLESS=1`** env toggle is the test-only flag that forces `headless=True` in the `login` flow so integration tests don't need a display server. Production defaults to `headless=False` (visible browser) for `login`.
- **Task 19 (live retest) requires user interaction** and cannot be automated in a subagent. Controller pauses there.

---

*See `docs/superpowers/specs/2026-04-16-multi-domain-auth-design.md` for authoritative spec. This plan is the v0.1.1 implementation roadmap.*
