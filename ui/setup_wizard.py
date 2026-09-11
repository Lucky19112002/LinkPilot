from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from bootstrap import run_first_launch, verify_environment
from config import load_config, save_config
from ollama_manager import OllamaManager


class SetupChecks(QObject):
    log = Signal(str)
    finished = Signal()
    completed = Signal(bool)
    cancelled = False

    def run(self) -> None:
        ok = run_first_launch(self.log.emit, lambda: self.cancelled)
        self.completed.emit(ok)
        self.finished.emit()


class SetupWizard(QWidget):
    def __init__(self):
        super().__init__()
        self.thread: QThread | None = None
        self.checks: SetupChecks | None = None
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        run = QPushButton("Run Setup")
        run.clicked.connect(self.run_checks)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel)
        start_ollama = QPushButton("Start Ollama Server")
        start_ollama.clicked.connect(self.start_ollama)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Setup"))
        layout.addWidget(run)
        layout.addWidget(cancel)
        layout.addWidget(start_ollama)
        layout.addWidget(self.output)
        if not load_config().first_launch_complete:
            QTimer.singleShot(0, self.run_checks)
        else:
            QTimer.singleShot(0, self.show_status)

    def run_checks(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        self.output.clear()
        self.thread = QThread()
        self.checks = SetupChecks()
        self.checks.moveToThread(self.thread)
        self.thread.started.connect(self.checks.run)
        self.checks.log.connect(self.output.appendPlainText)
        self.checks.completed.connect(self.mark_completed)
        self.checks.finished.connect(self.thread.quit)
        self.thread.finished.connect(lambda: setattr(self, "thread", None))
        self.thread.start()

    def show_status(self) -> None:
        self.output.clear()
        for name, ok in verify_environment().items():
            self.output.appendPlainText(f"{name}: {'OK' if ok else 'Missing'}")

    def cancel(self) -> None:
        if self.checks:
            self.checks.cancelled = True

    def start_ollama(self) -> None:
        manager = OllamaManager(load_config())
        if not manager.is_installed():
            webbrowser.open("https://ollama.com/download")
            self.output.appendPlainText("Ollama missing: opened official download page")
            return
        manager.start_server()
        self.output.appendPlainText("Ollama server start requested")

    def mark_completed(self, ok: bool) -> None:
        if ok:
            config = load_config()
            config.first_launch_complete = True
            save_config(config)

    def closeEvent(self, event) -> None:
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self) -> None:
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(3000)
