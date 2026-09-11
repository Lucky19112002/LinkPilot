from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget

from config import Config
from ollama_manager import OllamaManager


class ModelsPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.manager = OllamaManager(config)
        self.status = QLabel()
        self.list = QListWidget()
        refresh = QPushButton("Refresh")
        use = QPushButton("Use Selected")
        delete = QPushButton("Delete Selected")
        download = QPushButton("Download Model")
        refresh.clicked.connect(self.refresh)
        use.clicked.connect(self.use_selected)
        delete.clicked.connect(self.delete_selected)
        download.clicked.connect(self.download_model)
        buttons = QHBoxLayout()
        for button in (refresh, use, delete, download):
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        self.status.setText(
            f"Server: {'Running' if self.manager.is_running() else 'Stopped'} | "
            f"Ollama: {self.manager.version()} | Active: {self.config.active_model}"
        )
        try:
            for model in self.manager.list_models():
                active = "  Active" if model == self.config.active_model else ""
                self.list.addItem(f"{model}{active}")
        except Exception as exc:
            self.list.addItem(f"Ollama unavailable: {exc}")

    def use_selected(self) -> None:
        item = self.list.currentItem()
        if item:
            self.manager.set_active_model(item.text().replace("  Active", ""))
            self.refresh()

    def delete_selected(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        model = item.text().replace("  Active", "")
        try:
            self.manager.delete_model(model)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))

    def download_model(self) -> None:
        model, ok = QInputDialog.getText(self, "Download model", "Model name")
        if not ok or not model.strip():
            return
        try:
            self.manager.download_model(model.strip())
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Download failed", str(exc))
