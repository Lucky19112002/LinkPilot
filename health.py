from __future__ import annotations

import shutil

import psutil

from api import ApiClient
from bootstrap import active_model_ok, check_ollama, check_python, chromium_ok, packages_ok
from config import Config
from ollama_manager import OllamaManager


def missing_components(config: Config) -> list[str]:
    checks = {
        "Python runtime": check_python(),
        "Python packages": packages_ok(),
        "Ollama": check_ollama(),
        "Ollama server": OllamaManager(config).is_running(),
        f"Model {config.active_model}": active_model_ok(config),
        "Playwright Chromium": chromium_ok(),
    }
    return [name for name, ok in checks.items() if not ok]


def running_linkpilot_processes() -> list[str]:
    names = []
    wanted = ("linkpilot", "ollama", "chromium", "chrome", "msedge", "playwright")
    noise = ("crashpad", "helper")
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            name = process.info.get("name") or ""
            cmdline = " ".join(process.info.get("cmdline") or [])
            text = f"{name} {cmdline}".lower()
            if any(item in text for item in noise):
                continue
            if any(item in text for item in wanted):
                if name.lower() == "node" and "playwright" not in text:
                    continue
                label = name or cmdline.split(" ", 1)[0]
                if name.lower() == "node":
                    label = "Playwright driver"
                if label and label not in names:
                    names.append(label)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return names[:8]


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
