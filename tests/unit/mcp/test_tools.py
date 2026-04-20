"""Tool handler tests.

Tool handlers shell out to the CLI. We patch subprocess.run with canned
outputs to keep these unit-level fast and deterministic.
"""

from unittest.mock import patch

from webscraper.mcp_server.tools import (
    check_environment,
    forget_saved_login,
    list_saved_logins,
)


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_list_saved_logins_parses_stdout() -> None:
    fake_out = (
        "connectance.org                  14 cookies   expires in 29d\n"
        "notion.so                         8 cookies   session-only\n"
    )
    with patch(
        "webscraper.mcp_server.tools.subprocess.run", return_value=_FakeProc(0, stdout=fake_out)
    ):
        res = list_saved_logins()
    assert res["status"] == "ok"
    rows = res["key_data"]["sessions"]
    assert any(r["domain"] == "connectance.org" for r in rows)
    assert any(r["domain"] == "notion.so" for r in rows)


def test_forget_saved_login_reports_deleted() -> None:
    with patch(
        "webscraper.mcp_server.tools.subprocess.run",
        return_value=_FakeProc(0, stderr="forgot ex.com\n"),
    ):
        res = forget_saved_login(domain="ex.com")
    assert res["status"] == "ok"
    assert "ex.com" in res["summary"]


def test_check_environment_reports_issues_when_exit_4() -> None:
    stdout = "[  OK] Python 3.11\n[FAIL] Playwright: not installed\n[  OK] auth dir\n"
    with patch(
        "webscraper.mcp_server.tools.subprocess.run", return_value=_FakeProc(4, stdout=stdout)
    ):
        res = check_environment()
    assert res["status"] == "setup_issue"
    assert "Playwright" in " ".join(res["key_data"]["issues"])
