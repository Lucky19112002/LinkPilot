from datetime import datetime, timedelta
from pathlib import Path

from log_maintenance import maintain_logs


def test_log_rotation_compresses_old_run(tmp_path: Path):
    old = tmp_path / "2020-01-01_00-00-00"
    old.mkdir()
    (old / "execution.log").write_text("x", encoding="utf-8")
    ts = (datetime.now() - timedelta(days=40)).timestamp()
    import os

    os.utime(old, (ts, ts))
    maintain_logs(tmp_path, keep_days=30, max_gb=5)
    assert old.with_suffix(".zip").exists()
