from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from api import ApiClient
from bootstrap import active_model_ok, check_ollama, check_python, chromium_ok, install_chromium, packages_ok, start_ollama
from config import Config
from ollama_manager import OllamaManager
from updater import Updater


class DiagnosticsPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Item", "Status", "Repair"])
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(refresh)
        layout.addWidget(self.table)
        self.refresh()

    def checks(self) -> list[tuple[str, bool, callable]]:
        manager = OllamaManager(self.config)
        return [
            ("Python", check_python(), lambda: None),
            ("Packages", packages_ok(), lambda: None),
            ("Ollama", check_ollama(), lambda: None),
            ("Ollama Server", manager.is_running(), start_ollama),
            ("Chromium", chromium_ok(), install_chromium),
            ("Active Model", active_model_ok(self.config), lambda: manager.download_model(self.config.active_model)),
            ("API", self.api_ok(), lambda: ApiClient(self.config).login()),
            ("Update Service", Updater(self.config.update_url).check()["status"] in {"disabled", "current", "available"}, lambda: Updater(self.config.update_url).check()),
        ]

    def api_ok(self) -> bool:
        try:
            return bool(ApiClient(self.config).login().get("ok"))
        except Exception:
            return False

    def refresh(self) -> None:
        rows = self.checks()
        self.table.setRowCount(len(rows))
        for row, (name, ok, repair) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem("OK" if ok else "Missing"))
            button = QPushButton("Repair")
            button.clicked.connect(lambda _checked=False, fn=repair: self.repair(fn))
            self.table.setCellWidget(row, 2, button)

    def repair(self, fn) -> None:
        try:
            fn()
        finally:
            self.refresh()
