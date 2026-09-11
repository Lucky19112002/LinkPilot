from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from crash_handler import install_global_handler
from config import load_config
from log_maintenance import maintain_logs
from updater import Updater
from ui.main_window import MainWindow


def main() -> int:
    Updater().apply_pending()
    config = load_config()
    maintain_logs(keep_days=config.keep_logs_days, max_gb=config.max_logs_gb)
    install_global_handler()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
