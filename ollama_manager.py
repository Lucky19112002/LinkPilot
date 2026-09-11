from __future__ import annotations

import shutil
import subprocess
from typing import Any

import requests

from config import Config, save_config


class OllamaManager:
    def __init__(self, config: Config):
        self.config = config

    def is_installed(self) -> bool:
        return shutil.which("ollama") is not None

    def version(self) -> str:
        if not self.is_installed():
            return "Not installed"
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, check=False)
        return (result.stdout or result.stderr).strip() or "Unknown"

    def is_running(self) -> bool:
        try:
            return requests.get(f"{self.config.ollama_base_url}/api/tags", timeout=2).ok
        except requests.RequestException:
            return False

    def start_server(self) -> subprocess.Popen | None:
        if self.is_running() or not self.is_installed():
            return None
        return subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def list_models(self) -> list[str]:
        response = requests.get(f"{self.config.ollama_base_url}/api/tags", timeout=10)
        response.raise_for_status()
        return [model["name"] for model in response.json().get("models", [])]

    def download_model(self, model: str) -> None:
        subprocess.check_call(["ollama", "pull", model])

    def delete_model(self, model: str) -> None:
        subprocess.check_call(["ollama", "rm", model])

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
