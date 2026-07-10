"""Worker repo partitioning and slot-range disjointness for parallel drains."""

from harness.cli import worker_repos

REPOS = ["zustand", "click", "hono", "rich", "zod", "sql-formatter", "hugo",
         "eslint", "nushell", "prettier"]


def test_partitions_disjoint_and_cover():
    for workers in (1, 2, 3, 4):
        parts = [worker_repos(REPOS, workers, k) for k in range(workers)]
        seen = [r for part in parts for r in part]
        assert sorted(seen) == sorted(REPOS)
        assert len(seen) == len(set(seen))


def test_workers_one_returns_all_sorted():
    assert worker_repos(REPOS, 1, 0) == sorted(REPOS)


def test_deterministic_across_calls():
    assert worker_repos(REPOS, 3, 1) == worker_repos(REPOS, 3, 1)


def test_slot_ranges_disjoint_across_workers():
    slot_count = 2
    workers = 3
    all_slots: set[int] = set()
    for k in range(workers):
        mine = worker_repos(REPOS, workers, k)
        slots = {k * slot_count + (i % slot_count) for i, _ in enumerate(mine)}
        assert not (slots & all_slots)
        all_slots |= slots


def test_workers_one_reproduces_legacy_mapping():
    slot_count = 2
    mine = worker_repos(REPOS, 1, 0)
    new_mapping = {name: 0 * slot_count + (i % slot_count) for i, name in enumerate(mine)}
    legacy = {name: i % slot_count for i, name in enumerate(sorted(REPOS))}
    assert new_mapping == legacy
