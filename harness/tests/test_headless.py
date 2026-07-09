"""Shared headless helpers: the factoring out of runner.py must keep the
public surface identical, and the resume flag must reach the command line."""

import json
from datetime import datetime, timezone

import pytest

from harness import headless, runner

# Real error shape captured live from WI-E06 (Claude Code 2.1.175, exit 1):
# is_error with api_error_status 429, result text matching NO legacy
# rate-limit wording ("session limit", not "usage limit" / "rate limit").
RATE_LIMITED_429_RESULT = {
    "type": "result",
    "subtype": "success",
    "is_error": True,
    "api_error_status": 429,
    "duration_ms": 115161,
    "duration_api_ms": 109002,
    "num_turns": 35,
    "result": "You've hit your session limit • resets 4:50pm (America/Denver)",
    "stop_reason": "stop_sequence",
    "session_id": "30f7a294-526a-483e-b9c4-4384deb09e79",
    "total_cost_usd": 0.1517513,
}


class _FakeProc:
    def __init__(self, stdout: str, returncode: int):
        self.pid = 12345
        self.returncode = returncode
        self._stdout = stdout

    def communicate(self, timeout=None):
        return self._stdout, ""


def _patch_invoke(monkeypatch, stdout: str, returncode: int) -> None:
    monkeypatch.setattr("shutil.which", lambda _: "claude")
    monkeypatch.setattr(
        headless.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakeProc(stdout, returncode),
    )


def test_runner_reexports_headless_surface():
    # cli.py and older callers reference these through runner.*
    assert runner.RateLimited is headless.RateLimited
    assert runner.munge_cwd is headless.munge_cwd
    assert runner.invoke_claude is headless.invoke_claude
    assert runner.scrub_env is headless.scrub_env


def test_munge_cwd_replaces_non_alphanumerics():
    assert headless.munge_cwd(r"C:\Dev\x") == "C--Dev-x"
    assert headless.munge_cwd("/tmp/a b.c") == "-tmp-a-b-c"


def test_build_command_resume_flag(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "claude")
    base = headless.build_command("hi", "haiku")
    assert "-r" not in base
    resumed = headless.build_command("hi", "haiku", resume_session="sess-123")
    assert resumed[-2:] == ["-r", "sess-123"]
    assert resumed[:len(base)] == base


def test_looks_rate_limited():
    assert headless.looks_rate_limited(1, "usage limit reached")
    assert not headless.looks_rate_limited(0, "usage limit reached")
    assert not headless.looks_rate_limited(1, "syntax error")


def test_result_rate_limited_status_field():
    assert headless.result_rate_limited(RATE_LIMITED_429_RESULT)
    assert headless.result_rate_limited({"api_error_status": 429})
    assert headless.result_rate_limited({"api_error_status": "429 Too Many Requests"})
    # is_error true with a 429 in some other status-ish field
    assert headless.result_rate_limited({"is_error": True, "http_status": "429"})
    # is_error true but no 429 anywhere: a genuine run failure
    assert not headless.result_rate_limited({"is_error": True, "result": "boom"})
    # successful run whose text merely mentions 429 is not a rate limit
    assert not headless.result_rate_limited(
        {"is_error": False, "result": "handled the 429 retry logic"}
    )


def test_invoke_claude_429_status_raises_rate_limited(monkeypatch, tmp_path):
    """The real WI-E06 shape: exit 1, is_error JSON on stdout, api_error_status
    429, result wording that matches none of the legacy text patterns."""
    _patch_invoke(monkeypatch, json.dumps(RATE_LIMITED_429_RESULT), returncode=1)
    with pytest.raises(headless.RateLimited) as excinfo:
        headless.invoke_claude("hi", "haiku", tmp_path, timeout_s=5)
    resume = datetime.fromisoformat(excinfo.value.resume_after)
    assert resume > datetime.now(timezone.utc)


def test_invoke_claude_429_status_exit_zero_raises_rate_limited(monkeypatch, tmp_path):
    """Same JSON but exit 0: the is_error path must also gate on the status."""
    _patch_invoke(monkeypatch, json.dumps(RATE_LIMITED_429_RESULT), returncode=0)
    with pytest.raises(headless.RateLimited):
        headless.invoke_claude("hi", "haiku", tmp_path, timeout_s=5)


def test_invoke_claude_non_429_error_still_runtime_error(monkeypatch, tmp_path):
    result = {"type": "result", "is_error": True, "result": "tool crashed"}
    _patch_invoke(monkeypatch, json.dumps(result), returncode=0)
    with pytest.raises(RuntimeError) as excinfo:
        headless.invoke_claude("hi", "haiku", tmp_path, timeout_s=5)
    assert not isinstance(excinfo.value, headless.RateLimited)


def test_parse_resume_after_reset_hint_prefers_wall_clock():
    # 4:50pm America/Denver in July is 22:50 UTC (MDT, UTC-6).
    now = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
    out = headless.parse_resume_after(
        "You've hit your session limit • resets 4:50pm (America/Denver)", now=now
    )
    assert out == "2026-07-09T22:50:00+00:00"
    # A hint already in the past rolls to the next day.
    late = datetime(2026, 7, 9, 23, 30, tzinfo=timezone.utc)
    out_late = headless.parse_resume_after("resets 4:50pm (America/Denver)", now=late)
    assert out_late == "2026-07-10T22:50:00+00:00"


def test_parse_resume_after_fallback_is_60_minutes():
    now = datetime(2026, 7, 9, 20, 0, tzinfo=timezone.utc)
    assert (
        headless.parse_resume_after("no usable reset time here", now=now)
        == "2026-07-09T21:00:00+00:00"
    )


def test_scrub_env_drops_secrets(monkeypatch):
    monkeypatch.setenv("SOME_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "keep")
    env = headless.scrub_env()
    assert "SOME_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert env.get("CLAUDE_CONFIG_DIR") == "keep"
