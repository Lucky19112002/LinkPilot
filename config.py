from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from shutil import copy2

from paths import data_dir


CONFIG_PATH = data_dir() / "config.json"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")


@dataclass
class Config:
    ollama_host: str = "127.0.0.1"
    ollama_port: int = 11434
    active_model: str = "qwen2.5vl:7b"
    api_base_url: str = "https://swetpatel.bsite.net"
    api_username: str = ""
    credential_id: str = "default"
    headless: bool = False
    wait_after_task: int = 30
    max_ai_actions: int = 15
    recovery_attempts: int = 3
    human_typing: bool = True
    update_url: str = "https://api.github.com/repos/Lucky19112002/LinkPilot/releases/latest"
    worker_name: str = ""
    worker_id: str = ""
    location: str = ""
    notes: str = ""
    launch_on_login: bool = False
    first_launch_complete: bool = False
    build_number: str = "100"
    github_url: str = "https://github.com/linkpilot/linkpilot"
    keep_logs_days: int = 30
    max_logs_gb: float = 5.0
    browser_width: int = 1440
    browser_height: int = 900
    profile: dict[str, str] = field(
        default_factory=lambda: {
            "first_name": "Lucky",
            "last_name": "Patel",
            "email": "",
            "phone": "",
            "username": "",
            "address": "",
            "city": "",
            "zip": "",
            "message": "",
        }
    )

    @property
    def ollama_base_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        if DEFAULT_CONFIG_PATH.exists() and path == CONFIG_PATH:
            copy2(DEFAULT_CONFIG_PATH, path)
            return load_config(path)
        cfg = Config()
        save_config(cfg, path)
        return cfg
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("api_password"):
        from secure_store import SecureStore

        SecureStore().set_password(data.pop("api_password"), data.get("credential_id", "default"))
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if data.get("profile", {}).get("password"):
        from secure_store import SecureStore

        profile = dict(data["profile"])
        SecureStore().set_password(profile.pop("password"), f"{data.get('credential_id', 'default')}:profile_password")
        data["profile"] = profile
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    defaults = asdict(Config())
    defaults.update(data)
    if not defaults.get("update_url"):
        defaults["update_url"] = Config().update_url
    return Config(**defaults)


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
