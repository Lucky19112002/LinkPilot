from __future__ import annotations

import platform
import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget

from bootstrap import package_versions
from config import Config
from ollama_manager import OllamaManager
from version import APP_NAME, BUILD, VERSION


class AboutPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        copy = QPushButton("Copy Diagnostics")
        copy.clicked.connect(self.copy)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(APP_NAME))
        layout.addWidget(self.report)
        layout.addWidget(copy)
        self.refresh()

    def diagnostics(self) -> str:
        versions = package_versions()
        lines = [
            f"{APP_NAME} version: {VERSION}",
            f"Build number: {BUILD}",
            f"Python: {sys.version.split()[0]}",
            f"Ollama: {OllamaManager(self.config).version()}",
            f"Playwright: {versions.get('playwright', 'missing')}",
            f"OS: {platform.platform()}",
            f"Worker ID: {self.config.worker_id}",
            "License: Proprietary",
            f"GitHub: {self.config.github_url}",
        ]
        return "\n".join(lines)

    def refresh(self) -> None:
        self.report.setPlainText(self.diagnostics())

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.diagnostics())
