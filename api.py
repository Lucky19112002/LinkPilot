from __future__ import annotations

from urllib.parse import urljoin

import requests
from urllib3.exceptions import InsecureRequestWarning

from config import Config
from secure_store import SecureStore


class ApiClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.verify = not config.allow_insecure_https
        if config.allow_insecure_https:
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        self.store = SecureStore()

    def _url(self, path: str) -> str:
        return urljoin(self.config.api_base_url.rstrip("/") + "/", path.lstrip("/"))

    def login(self) -> dict:
        response = self.session.post(
            self._url("auth.ashx"),
            data=self.with_worker({"username": self.config.api_username, "password": self.store.get_password(self.config.credential_id)}),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def fetch_urls(self) -> list[str]:
        response = self.session.get(self._url("urls.ashx"), params=self.worker_identity(), timeout=30)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [str(item.get("url", item)) if isinstance(item, dict) else str(item) for item in payload]
        return [str(item.get("url", item)) for item in payload.get("urls", [])]

    def send_error(self, message: str, url: str = "") -> None:
        response = self.session.post(self._url("logs.ashx"), json=self.with_worker({"url": url, "error": message}), timeout=20)
        response.raise_for_status()

    def send_result(self, result: dict) -> None:
        response = self.session.post(self._url("result.ashx"), json=self.with_worker(result), timeout=20)
        response.raise_for_status()

    def heartbeat_payload(self, payload: dict) -> None:
        response = self.session.post(self._url("heartbeat.ashx"), json=self.with_worker(payload), timeout=10)
        response.raise_for_status()

    def heartbeat(self) -> bool:
        response = self.session.get(self._url("auth.ashx"), timeout=10)
        return response.ok

    def worker_identity(self) -> dict:
        return {
            "worker_name": self.config.worker_name,
            "worker_id": self.config.worker_id,
            "location": self.config.location,
            "notes": self.config.notes,
        }

    def with_worker(self, data: dict) -> dict:
        merged = dict(data)
        merged.update(self.worker_identity())
        return merged
