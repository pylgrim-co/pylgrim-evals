"""Schedule generation: determinism and the rep-blocking property."""

from harness import schedule

TASKS = [
    {"task_id": "alpha-t01", "repo": "alpha"},
    {"task_id": "alpha-t02", "repo": "alpha"},
    {"task_id": "beta-t01", "repo": "beta"},
]
ARMS = ["vanilla", "claudemd"]
MODELS = ["sonnet", "haiku"]


def test_same_seed_identical_schedule():
    a = schedule.generate(TASKS, ARMS, MODELS, reps=3, seed=42)
    b = schedule.generate(TASKS, ARMS, MODELS, reps=3, seed=42)
    assert a == b


def test_different_seed_different_order():
    a = schedule.generate(TASKS, ARMS, MODELS, reps=3, seed=42)
    b = schedule.generate(TASKS, ARMS, MODELS, reps=3, seed=43)
    assert [r["run_id"] for r in a] != [r["run_id"] for r in b]
    # Same set of runs regardless of seed.
    assert {r["run_id"] for r in a} == {r["run_id"] for r in b}


def test_rep_blocking():
    reps = 3
    rows = schedule.generate(TASKS, ARMS, MODELS, reps=reps, seed=1)
    cells_per_block = len(TASKS) * len(ARMS) * len(MODELS)
    assert len(rows) == cells_per_block * reps

    # order_keys are contiguous 0..n-1 in row order.
    assert [r["order_key"] for r in rows] == list(range(len(rows)))

    # All rep-k runs occupy one contiguous order_key block, in rep order,
    # and each block covers every (task, arm, model) cell exactly once.
    for rep in range(1, reps + 1):
        block = [r for r in rows if r["rep"] == rep]
        keys = sorted(r["order_key"] for r in block)
        expected_start = (rep - 1) * cells_per_block
        assert keys == list(range(expected_start, expected_start + cells_per_block))
        cells = {(r["task_id"], r["arm"], r["model"]) for r in block}
        assert len(cells) == cells_per_block


def test_shuffled_within_block():
    rows = schedule.generate(TASKS, ARMS, MODELS, reps=1, seed=42)
    unshuffled = [
        (t["task_id"], arm, model) for t in TASKS for arm in ARMS for model in MODELS
    ]
    assert [(r["task_id"], r["arm"], r["model"]) for r in rows] != unshuffled


def test_run_ids_and_seeds_stable():
    rows = schedule.generate(TASKS, ARMS, MODELS, reps=2, seed=42)
    by_id = {r["run_id"]: r for r in rows}
    assert "alpha-t01--vanilla--sonnet--r1" in by_id
    row = by_id["alpha-t01--vanilla--sonnet--r1"]
    assert row["repo"] == "alpha"
    # Per-run seed is a pure function of (master seed, run_id).
    again = schedule.generate(TASKS, ARMS, MODELS, reps=2, seed=42)
    assert {r["run_id"]: r["seed"] for r in again} == {r["run_id"]: r["seed"] for r in rows}


def test_order_key_start_appends_without_overlap():
    main = schedule.generate(TASKS, ARMS, MODELS, reps=2, seed=42)
    controls = schedule.generate(
        [{"task_id": "alpha-c01", "repo": "alpha"}],
        ARMS,
        MODELS,
        reps=1,
        seed=42,
        order_key_start=len(main),
    )
    main_keys = {r["order_key"] for r in main}
    control_keys = {r["order_key"] for r in controls}
    assert not (main_keys & control_keys)
    assert min(control_keys) == len(main)
    assert max(control_keys) == len(main) + len(controls) - 1


def test_order_key_start_default_zero_unchanged():
    rows = schedule.generate(TASKS, ARMS, MODELS, reps=1, seed=42)
    baseline = schedule.generate(TASKS, ARMS, MODELS, reps=1, seed=42, order_key_start=0)
    assert rows == baseline
