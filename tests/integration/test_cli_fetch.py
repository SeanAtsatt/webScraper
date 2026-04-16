"""CLI integration tests for `webscraper fetch`."""

import json
import subprocess
import sys


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "webscraper", *args],
        capture_output=True,
        text=True,
        timeout=60,
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
    result = _run(
        "fetch", f"{fixture_server}/static/article", "--tier=fast", "--out", str(out_file)
    )
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
