from __future__ import annotations

import shutil

import psutil

from api import ApiClient
from config import Config
from ollama_manager import OllamaManager


def health_warnings(config: Config) -> list[str]:
    warnings = []
    if not OllamaManager(config).is_running():
        warnings.append("Ollama disconnected")
    try:
        ApiClient(config).heartbeat()
    except Exception:
        warnings.append("API unreachable")
    disk = shutil.disk_usage(".")
    if disk.free / disk.total < 0.1:
        warnings.append("Low disk space")
    if psutil.virtual_memory().percent > 90:
        warnings.append("Memory pressure")
    return warnings
