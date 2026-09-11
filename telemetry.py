from __future__ import annotations

import platform
from time import monotonic

import psutil

from api import ApiClient
from config import Config
from version import VERSION


class Telemetry:
    def __init__(self, config: Config):
        self.config = config
        self.last_sent = 0.0

    def maybe_send(self, api: ApiClient, status: str, current_url: str = "") -> None:
        now = monotonic()
        if now - self.last_sent < 60:
            return
        self.last_sent = now
        api.heartbeat_payload(self.payload(status, current_url))

    def payload(self, status: str, current_url: str = "") -> dict:
        return {
            "worker_id": self.config.worker_id or platform.node(),
            "worker_name": self.config.worker_name,
            "location": self.config.location,
            "notes": self.config.notes,
            "status": status,
            "cpu": psutil.cpu_percent(interval=None),
            "ram": round(psutil.virtual_memory().used / (1024**3), 2),
            "current_url": current_url,
            "model": self.config.active_model,
            "version": VERSION,
        }
