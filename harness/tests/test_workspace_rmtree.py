import stat
from pathlib import Path

from harness import workspace


def test_force_rmtree_clears_readonly(tmp_path):
    d = tmp_path / "slot"
    (d / "store").mkdir(parents=True)
    f = d / "store" / "ro.bin"
    f.write_bytes(b"x")
    f.chmod(stat.S_IREAD)
    workspace._force_rmtree(d)
    assert not d.exists()


def test_force_rmtree_missing_is_noop(tmp_path):
    workspace._force_rmtree(tmp_path / "nope")
