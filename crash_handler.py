from __future__ import annotations

import json
import sys
import traceback as tb
from datetime import datetime
from pathlib import Path

from version import VERSION
from paths import data_dir


CRASH_DIR = data_dir() / "logs" / "crashes"


def install_global_handler(callback=None) -> None:
    def handle(exc_type, exc, trace):
        report = save_crash(exc, "".join(tb.format_exception(exc_type, exc, trace)))
        if callback:
            callback(report)
        else:
            sys.__excepthook__(exc_type, exc, trace)

    sys.excepthook = handle


def save_crash(exception: BaseException, trace: str = "", current_url: str = "", worker_state: str = "", screenshot: bytes | None = None, memory: dict | None = None) -> Path:
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = CRASH_DIR / f"crash_{stamp}.json"
    data = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "version": VERSION,
        "exception": str(exception),
        "traceback": trace,
        "current_url": current_url,
        "worker_state": worker_state,
        "memory": memory or {},
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if screenshot:
        (CRASH_DIR / f"crash_{stamp}.png").write_bytes(screenshot)
    return path
