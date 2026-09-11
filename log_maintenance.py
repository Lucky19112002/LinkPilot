from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from paths import data_dir


def maintain_logs(root: Path | None = None, keep_days: int = 30, max_gb: float = 5.0) -> None:
    root = root or data_dir() / "logs"
    root.mkdir(exist_ok=True)
    cutoff = datetime.now() - timedelta(days=keep_days)
    for item in root.iterdir():
        if not item.is_dir() or item.name == "crashes":
            continue
        mtime = datetime.fromtimestamp(item.stat().st_mtime)
        if mtime < cutoff and not item.with_suffix(".zip").exists():
            with zipfile.ZipFile(item.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
                for path in item.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(root))
            shutil.rmtree(item)
    while folder_size(root) > max_gb * 1024**3:
        candidates = sorted((p for p in root.iterdir() if p.name != "crashes"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            return
        victim = candidates[0]
        shutil.rmtree(victim) if victim.is_dir() else victim.unlink()


def folder_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
