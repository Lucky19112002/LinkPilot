from __future__ import annotations

import json
import time
from pathlib import Path

import psutil
from PySide6.QtWidgets import QFileDialog, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget

from browser import BrowserEngine
from config import Config
from ollama_manager import OllamaManager


class BenchmarkPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.result: dict = {}
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        run = QPushButton("Run Benchmark")
        export = QPushButton("Export Benchmark JSON")
        run.clicked.connect(self.run)
        export.clicked.connect(self.export)
        layout = QVBoxLayout(self)
        layout.addWidget(run)
        layout.addWidget(export)
        layout.addWidget(self.output)

    def run(self) -> None:
        self.result = {"ram_gb": round(psutil.virtual_memory().used / 1024**3, 2)}
        start = time.monotonic()
        try:
            OllamaManager(self.config).generate_action("Return JSON {\"ok\":true}", "")
            self.result["ollama_latency"] = round(time.monotonic() - start, 3)
        except Exception as exc:
            self.result["ollama_error"] = str(exc)
        browser = BrowserEngine(Config(headless=True, human_typing=False))
        try:
            browser.launch()
            browser.goto((Path("tests/websites/registration.html")).resolve().as_uri())
            _, dom = browser.page_snapshot([])
            shot = Path("benchmark_step.png")
            browser.screenshot(shot)
            elements = browser.extract_elements()
            overlay = browser.overlay_screenshot(shot, Path("benchmark_overlay.png"), elements)
            self.result.update({"dom_extraction": round(dom, 3), "vision_overlay": round(overlay, 3)})
        finally:
            browser.close()
        self.output.setPlainText(json.dumps(self.result, indent=2))

    def export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Benchmark", "benchmark.json", "JSON Files (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.result, indent=2), encoding="utf-8")
