from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

from config import Config, save_config


def ollama_executable() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    paths = [
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
    ]
    if sys.platform == "win32":
        paths += [
            str(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"),
            str(Path.home() / "AppData" / "Local" / "Ollama" / "ollama.exe"),
        ]
    return next((path for path in paths if Path(path).exists()), None)


def start_detached(command: list[str]) -> subprocess.Popen:
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


class OllamaManager:
    def __init__(self, config: Config):
        self.config = config

    def is_installed(self) -> bool:
        return ollama_executable() is not None

    def version(self) -> str:
        exe = ollama_executable()
        if not exe:
            return "Not installed"
        result = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
        return (result.stdout or result.stderr).strip() or "Unknown"

    def is_running(self) -> bool:
        try:
            return requests.get(f"{self.config.ollama_base_url}/api/tags", timeout=2).ok
        except requests.RequestException:
            return False

    def start_server(self) -> subprocess.Popen | None:
        exe = ollama_executable()
        if self.is_running() or not exe:
            return None
        return start_detached([exe, "serve"])

    def list_models(self) -> list[str]:
        response = requests.get(f"{self.config.ollama_base_url}/api/tags", timeout=10)
        response.raise_for_status()
        return [model["name"] for model in response.json().get("models", [])]

    def download_model(self, model: str) -> None:
        subprocess.check_call([ollama_executable() or "ollama", "pull", model])

    def delete_model(self, model: str) -> None:
        subprocess.check_call([ollama_executable() or "ollama", "rm", model])

    def set_active_model(self, model: str) -> None:
        self.config.active_model = model
        save_config(self.config)

    def generate_action(self, prompt: str, image_b64: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.config.ollama_base_url}/api/generate",
            json={
                "model": self.config.active_model,
                "prompt": prompt,
                "images": [image_b64],
                "format": "json",
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
