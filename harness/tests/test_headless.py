"""Shared headless helpers: the factoring out of runner.py must keep the
public surface identical, and the resume flag must reach the command line."""

from harness import headless, runner


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


def test_scrub_env_drops_secrets(monkeypatch):
    monkeypatch.setenv("SOME_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "keep")
    env = headless.scrub_env()
    assert "SOME_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert env.get("CLAUDE_CONFIG_DIR") == "keep"
