from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
from paths import data_dir


class LogsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.list = QListWidget()
        self.files = QListWidget()
        self.timeline = QListWidget()
        self.image = QLabel()
        self.image.setMinimumHeight(220)
        self.image.setScaledContents(True)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        refresh = QPushButton("Refresh")
        open_folder = QPushButton("Open Folder")
        refresh.clicked.connect(self.refresh)
        open_folder.clicked.connect(self.open_folder)
        self.list.currentTextChanged.connect(self.show_run)
        self.files.currentTextChanged.connect(self.show_file)
        self.timeline.currentTextChanged.connect(self.show_step)
        top = QHBoxLayout()
        top.addWidget(refresh)
        top.addWidget(open_folder)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(QLabel("Runs"))
        layout.addWidget(self.list)
        layout.addWidget(QLabel("Files"))
        layout.addWidget(self.files)
        layout.addWidget(QLabel("Timeline"))
        layout.addWidget(self.timeline)
        layout.addWidget(self.image)
        layout.addWidget(self.preview)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        root = data_dir() / "logs"
        root.mkdir(exist_ok=True)
        for item in sorted(root.iterdir(), reverse=True):
            if item.is_dir():
                self.list.addItem(item.name)

    def selected_run(self) -> Path | None:
        item = self.list.currentItem()
        return data_dir() / "logs" / item.text() if item else None

    def show_run(self, *_args) -> None:
        self.files.clear()
        self.timeline.clear()
        self.preview.clear()
        self.image.clear()
        run = self.selected_run()
        if not run:
            return
        for file in sorted(path for path in run.rglob("*") if path.is_file()):
            if file.suffix.lower() in {".log", ".txt", ".json", ".png"}:
                self.files.addItem(str(file.relative_to(run)))
        for timeline in run.rglob("timeline.json"):
            try:
                import json

                for item in json.loads(timeline.read_text(encoding="utf-8")):
                    label = f"Step {item.get('step')}  {item.get('action')}  {item.get('element', '')}"
                    self.timeline.addItem(f"{timeline.parent.relative_to(run)}|{label}")
            except Exception:
                continue

    def show_file(self, *_args) -> None:
        run = self.selected_run()
        item = self.files.currentItem()
        if not run or not item:
            return
        path = run / item.text()
        if path.suffix.lower() == ".png":
            self.show_image(path)
        else:
            self.preview.setPlainText(path.read_text(encoding="utf-8", errors="replace"))

    def show_step(self, *_args) -> None:
        run = self.selected_run()
        item = self.timeline.currentItem()
        if not run or not item:
            return
        folder = item.text().split("|", 1)[0]
        step = item.text().split("Step ", 1)[1].split(" ", 1)[0]
        base = run / folder
        shot = base / f"step{step}.png"
        self.show_image(shot)
        parts = []
        for name in (f"llm_prompt_step{step}.txt", f"llm_raw_step{step}.txt", f"llm_decision_step{step}.json"):
            path = base / name
            if path.exists():
                parts.append(f"{name}\n{path.read_text(encoding='utf-8', errors='replace')}")
        self.preview.setPlainText("\n\n".join(parts))

    def show_image(self, path: Path) -> None:
        self.preview.setPlainText(str(path.resolve()))
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.image.setPixmap(pixmap)

    def open_folder(self) -> None:
        run = self.selected_run() or data_dir() / "logs"
        run.mkdir(exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(run.resolve())])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(run.resolve())])
        else:
            subprocess.Popen(["xdg-open", str(run.resolve())])
