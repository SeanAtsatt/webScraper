"""Error translator tests."""

import json

from webscraper.mcp_server.errors import classify_cli_result


# [F-REQ-040]
def test_classify_ok_when_exit_zero() -> None:
    r = classify_cli_result(returncode=0, stdout="{}", stderr="")
    assert r["status"] == "ok"


# [F-REQ-040]
def test_classify_bad_url_on_exit_3() -> None:
    r = classify_cli_result(returncode=3, stdout="", stderr="usage error: bad url")
    assert r["status"] == "bad_url"
    assert "URL" in r["summary"]


# [F-REQ-045]
def test_classify_setup_issue_on_exit_4() -> None:
    r = classify_cli_result(returncode=4, stdout='{"error": {"type": "environment"}}', stderr="")
    assert r["status"] == "setup_issue"


# [F-REQ-046]
def test_classify_auth_required_on_login_redirect() -> None:
    stdout = json.dumps(
        {
            "error": {
                "type": "fetch_failed",
                "message": "all tiers failed: ['http_403']",
            }
        }
    )
    r = classify_cli_result(
        returncode=2, stdout=stdout, stderr="", final_url="https://ex.com/login"
    )
    assert r["status"] == "auth_required"
    assert r["suggested_next"] == "log_in_to_site"


# [F-REQ-047]
def test_classify_bot_protection_on_challenge_reason() -> None:
    stdout = json.dumps(
        {
            "error": {
                "type": "fetch_failed",
                "message": "all tiers failed: ['challenge:cloudflare']",
            }
        }
    )
    r = classify_cli_result(returncode=2, stdout=stdout, stderr="")
    assert r["status"] == "bot_protection"


# [F-REQ-040]
def test_classify_fetch_failed_on_insufficient_content() -> None:
    stdout = json.dumps(
        {
            "error": {
                "type": "fetch_failed",
                "message": "all tiers failed: ['insufficient_content']",
            }
        }
    )
    r = classify_cli_result(returncode=2, stdout=stdout, stderr="")
    assert r["status"] == "fetch_failed"


# [F-REQ-041]
def test_classify_partial_fail_on_exit_5() -> None:
    r = classify_cli_result(returncode=5, stdout="", stderr="some pages failed")
    assert r["status"] == "partial_ok"
