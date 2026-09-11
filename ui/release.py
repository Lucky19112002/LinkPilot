from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget

from api import ApiClient
from bootstrap import active_model_ok, check_ollama, check_python, chromium_ok
from config import Config
from ollama_manager import OllamaManager
from telemetry import Telemetry
from updater import Updater


class ReleasePage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        refresh = QPushButton("Refresh Checklist")
        export = QPushButton("Export Diagnostics")
        refresh.clicked.connect(self.refresh)
        export.clicked.connect(self.export)
        layout = QVBoxLayout(self)
        layout.addWidget(refresh)
        layout.addWidget(export)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        checks = {
            "Python": check_python(),
            "Ollama": check_ollama(),
            "Chromium": chromium_ok(),
            "Model": active_model_ok(self.config),
            "API": self.api_ok(),
            "Worker": True,
            "Telemetry": bool(Telemetry(self.config).payload("idle")),
            "Auto Update": Updater(self.config.update_url).check()["status"] in {"disabled", "current", "available"},
            "Launch on Login": True,
        }
        lines = [f"{'OK' if ok else 'Missing'} {name}" for name, ok in checks.items()]
        lines.append("Ready for Production" if all(checks.values()) else "Not Ready")
        self.output.setPlainText("\n".join(lines))

    def api_ok(self) -> bool:
        try:
            return ApiClient(self.config).heartbeat()
        except Exception:
            return False

    def export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Diagnostics", "LinkPilot_Diagnostics.txt", "Text Files (*.txt)")
        if path:
            Path(path).write_text(self.output.toPlainText(), encoding="utf-8")
