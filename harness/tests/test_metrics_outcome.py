"""Outcome metric: trivial shell commands only, no repo or agent involved."""

from harness.metrics import tests_outcome


def test_exit_zero_passes(tmp_path):
    result = tests_outcome.compute("exit 0", tmp_path)
    assert result["passed"] is True
    assert result["test"]["exit_code"] == 0
    assert result["test"]["timed_out"] is False


def test_exit_nonzero_fails(tmp_path):
    result = tests_outcome.compute("exit 3", tmp_path)
    assert result["passed"] is False
    assert result["test"]["exit_code"] == 3


def test_deterministic_checks_all_must_pass(tmp_path):
    result = tests_outcome.compute("exit 0", tmp_path, deterministic_checks=["exit 1"])
    assert result["passed"] is False
    assert result["deterministic_checks"][0]["passed"] is False


def test_no_test_command_with_passing_checks(tmp_path):
    result = tests_outcome.compute("", tmp_path, deterministic_checks=["exit 0"])
    assert result["passed"] is True
    assert result["test"] is None
