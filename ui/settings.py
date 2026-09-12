from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFileDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget

from api import ApiClient
from config import Config, save_config
from secure_store import SecureStore
from service import set_launch_on_login


class SettingsPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.host = QLineEdit(config.ollama_host)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(config.ollama_port)
        self.model = QLineEdit(config.active_model)
        self.api_base = QLineEdit(config.api_base_url)
        self.username = QLineEdit(config.api_username)
        self.credential_id = QLineEdit(config.credential_id)
        self.password = QLineEdit(SecureStore().get_password(config.credential_id))
        self.password.setEchoMode(QLineEdit.Password)
        self.allow_insecure_https = QCheckBox()
        self.allow_insecure_https.setChecked(config.allow_insecure_https)
        self.worker_name = QLineEdit(config.worker_name)
        self.worker_id = QLineEdit(config.worker_id)
        self.location = QLineEdit(config.location)
        self.notes = QLineEdit(config.notes)
        self.launch_on_login = QCheckBox()
        self.launch_on_login.setChecked(config.launch_on_login)
        self.headless = QCheckBox()
        self.headless.setChecked(config.headless)
        self.wait = QSpinBox()
        self.wait.setRange(0, 3600)
        self.wait.setValue(config.wait_after_task)
        self.max_actions = QSpinBox()
        self.max_actions.setRange(1, 20)
        self.max_actions.setValue(config.max_ai_actions)
        self.keep_logs = QSpinBox()
        self.keep_logs.setRange(1, 365)
        self.keep_logs.setValue(config.keep_logs_days)
        self.max_logs = QSpinBox()
        self.max_logs.setRange(1, 100)
        self.max_logs.setValue(int(config.max_logs_gb))
        self.status = QLabel("")
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        test = QPushButton("Test Connection")
        test.clicked.connect(self.test_connection)
        export = QPushButton("Export Profile")
        export.clicked.connect(self.export_config)
        import_ = QPushButton("Import Config")
        import_.clicked.connect(self.import_config)

        layout = QFormLayout(self)
        for label, widget in (
            ("Ollama host", self.host),
            ("Ollama port", self.port),
            ("Active model", self.model),
            ("API base URL", self.api_base),
            ("API username", self.username),
            ("Credential ID", self.credential_id),
            ("API password", self.password),
            ("Allow insecure HTTPS", self.allow_insecure_https),
            ("Worker Name", self.worker_name),
            ("Worker ID", self.worker_id),
            ("Location", self.location),
            ("Notes", self.notes),
            ("Launch on Login", self.launch_on_login),
            ("Headless", self.headless),
            ("Wait after task", self.wait),
            ("Max AI actions", self.max_actions),
            ("Keep logs days", self.keep_logs),
            ("Max logs GB", self.max_logs),
        ):
            layout.addRow(label, widget)
        layout.addRow(save, test)
        layout.addRow(export, import_)
        layout.addRow("Status", self.status)

    def save(self) -> None:
        self.config.ollama_host = self.host.text()
        self.config.ollama_port = self.port.value()
        self.config.active_model = self.model.text()
        self.config.api_base_url = self.api_base.text()
        self.config.api_username = self.username.text()
        self.config.credential_id = self.credential_id.text() or "default"
        self.config.allow_insecure_https = self.allow_insecure_https.isChecked()
        SecureStore().set_password(self.password.text(), self.config.credential_id)
        self.config.worker_name = self.worker_name.text()
        self.config.worker_id = self.worker_id.text()
        self.config.location = self.location.text()
        self.config.notes = self.notes.text()
        self.config.launch_on_login = self.launch_on_login.isChecked()
        self.config.headless = self.headless.isChecked()
        self.config.wait_after_task = self.wait.value()
        self.config.max_ai_actions = self.max_actions.value()
        self.config.keep_logs_days = self.keep_logs.value()
        self.config.max_logs_gb = float(self.max_logs.value())
        save_config(self.config)
        try:
            set_launch_on_login(self.config.launch_on_login)
        except Exception as exc:
            self.status.setText(f"Saved; launch-on-login failed: {exc}")
            return
        self.status.setText("Saved")

    def test_connection(self) -> None:
        self.save()
        ok = False
        try:
            ok = bool(ApiClient(self.config).login().get("ok"))
        except Exception as exc:
            ok = False
            self.status.setText(f"Server unreachable: {exc}")
        else:
            self.status.setText("Connected" if ok else "Invalid credentials")
        self.api_base.setStyleSheet("background:#d7ffd9" if ok else "background:#ffd9d9")

    def export_config(self) -> None:
        self.save()
        path, _ = QFileDialog.getSaveFileName(self, "Export Profile", "linkpilot_profile.lpp", "LinkPilot Profile (*.lpp);;JSON Files (*.json)")
        if not path:
            return
        data = asdict(self.config)
        data.pop("profile", None)
        data["export_type"] = "linkpilot_profile"
        Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self.status.setText("Profile exported")

    def import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Config", "", "JSON Files (*.json)")
        if not path:
            return
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for key, value in data.items():
            if hasattr(self.config, key) and key not in {"profile"}:
                setattr(self.config, key, value)
        save_config(self.config)
        self.status.setText("Config imported; restart or reopen Settings to view")
