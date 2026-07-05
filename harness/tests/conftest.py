"""Shared fixtures: paths to synthetic artifacts and a loaded good task card."""

from pathlib import Path

import pytest

from harness import taskcards

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def good_task() -> taskcards.TaskCard:
    card, errors = taskcards.load_task_card(FIXTURES / "task_good.yaml")
    assert card is not None and errors == []
    return card


@pytest.fixture
def sample_diff() -> str:
    return (FIXTURES / "sample.diff").read_text(encoding="utf-8")
