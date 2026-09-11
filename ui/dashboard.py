from __future__ import annotations

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from config import Config
from health import health_warnings
from ollama_manager import OllamaManager
from updater import Updater
from worker import LinkPilotWorker


class DashboardPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.thread: QThread | None = None
        self.worker: LinkPilotWorker | None = None
        self.status = QLabel("Worker: Idle")
        self.current_url = QLabel("Current URL: -")
        self.queue = QLabel("Queue: 0")
        self.step = QLabel("AI Step: -")
        self.action = QLabel("Current Action: -")
        self.page_title = QLabel("Page Title: -")
        self.result = QLabel("Final Result: -")
        self.metrics = QLabel("Metrics: -")
        self.update_status = QLabel("Updater: checking")
        self.health = QLabel("Health: checking")
        self.step_progress = QProgressBar()
        self.step_progress.setRange(0, config.max_ai_actions)
        self.queue_table = QTableWidget(0, 3)
        self.queue_table.setHorizontalHeaderLabels(["URL", "Status", "Attempts"])
        self.ollama = QLabel(self._ollama_status())
        self.model = QLabel(f"Model: {config.active_model}")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.start = QPushButton("Start Worker")
        self.stop = QPushButton("Stop Worker")
        self.pause = QPushButton("Pause Queue")
        self.retry = QPushButton("Retry Selected")
        self.skip = QPushButton("Skip Selected")
        self.stop.setEnabled(False)
        self.start.clicked.connect(self.start_worker)
        self.stop.clicked.connect(self.stop_worker)
        self.pause.clicked.connect(self.pause_queue)
        self.retry.clicked.connect(self.retry_selected)
        self.skip.clicked.connect(self.skip_selected)

        layout = QVBoxLayout(self)
        for widget in (
            self.status,
            self.current_url,
            self.queue,
            self.step,
            self.action,
            self.page_title,
            self.result,
            self.metrics,
            self.update_status,
            self.health,
            self.step_progress,
            self.queue_table,
            self.ollama,
            self.model,
            self.start,
            self.stop,
            self.pause,
            self.retry,
            self.skip,
            self.logs,
        ):
            layout.addWidget(widget)
        layout.addStretch()
        QTimer.singleShot(0, self.check_update)
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self.check_health)
        self.health_timer.start(10000)
        QTimer.singleShot(0, self.check_health)

    def _ollama_status(self) -> str:
        return "Ollama: Connected" if OllamaManager(self.config).is_running() else "Ollama: Not connected"

    def start_worker(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        self.thread = QThread()
        self.worker = LinkPilotWorker(self.config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run_until_empty)
        self.worker.status_changed.connect(self.set_status)
        self.worker.current_url.connect(lambda url: self.current_url.setText(f"Current URL: {url}"))
        self.worker.queue_count.connect(lambda count: self.queue.setText(f"Queue: {count}"))
        self.worker.step_changed.connect(self.set_step)
        self.worker.action_changed.connect(lambda text: self.action.setText(f"Current Action: {text}"))
        self.worker.page_title_changed.connect(lambda text: self.page_title.setText(f"Page Title: {text}"))
        self.worker.result_changed.connect(lambda text: self.result.setText(f"Final Result: {text}"))
        self.worker.metrics_changed.connect(self.metrics.setText)
        self.worker.queue_changed.connect(self.update_queue)
        self.worker.progress.connect(lambda done: self.logs.appendPlainText(f"Processed: {done}"))
        self.worker.log.connect(self.logs.appendPlainText)
        self.worker.error.connect(lambda text: self.logs.appendPlainText(f"Notification: {text}"))
        self.worker.finished.connect(self.worker_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.start.setEnabled(False)
        self.stop.setEnabled(True)

    def stop_worker(self) -> None:
        if self.worker:
            self.worker.stop()
        self.status.setText("Worker: Stopping")

    def set_status(self, text: str) -> None:
        self.status.setText(f"Worker: {text}")

    def set_step(self, current: int, maximum: int) -> None:
        self.step.setText(f"AI Step: {current}/{maximum}")
        self.step_progress.setRange(0, maximum)
        self.step_progress.setValue(current)

    def worker_finished(self) -> None:
        self.start.setEnabled(True)
        self.stop.setEnabled(False)
        self.thread = None
        self.worker = None

    def update_queue(self, rows: list) -> None:
        self.queue_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                self.queue_table.setItem(row, col, QTableWidgetItem(str(value)))

    def selected_url(self) -> str:
        row = self.queue_table.currentRow()
        item = self.queue_table.item(row, 0) if row >= 0 else None
        return item.text() if item else ""

    def pause_queue(self) -> None:
        if not self.worker:
            return
        paused = self.pause.text().startswith("Pause")
        self.worker.set_paused(paused)
        self.pause.setText("Resume Queue" if paused else "Pause Queue")

    def retry_selected(self) -> None:
        if self.worker and self.selected_url():
            self.worker.retry_url(self.selected_url())

    def skip_selected(self) -> None:
        if self.worker and self.selected_url():
            self.worker.skip_url(self.selected_url())

    def check_update(self) -> None:
        try:
            status = Updater(self.config.update_url).check()
            text = status["status"]
            if status.get("latest"):
                text += f" {status['latest']}"
            self.update_status.setText(f"Updater: {text}")
        except Exception as exc:
            self.update_status.setText(f"Updater: {exc}")

    def check_health(self) -> None:
        warnings = health_warnings(self.config)
        self.health.setText("Health: OK" if not warnings else "Health: " + " | ".join(warnings))

    def cleanup(self) -> None:
        if self.worker:
            self.worker.stop()
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(3000)
