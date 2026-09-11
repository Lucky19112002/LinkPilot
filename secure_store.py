from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

try:
    import keyring
except Exception:  # pragma: no cover
    keyring = None


SERVICE = "LinkPilot"
FALLBACK_DIR = Path.home() / ".linkpilot"
KEY_PATH = FALLBACK_DIR / "secrets.key"
SECRETS_PATH = FALLBACK_DIR / "secrets.json"


class SecureStore:
    def __init__(self, service: str = SERVICE):
        self.service = service

    def get_password(self, credential_id: str = "default") -> str:
        if keyring:
            try:
                value = keyring.get_password(self.service, credential_id)
                if value:
                    return value
            except Exception:
                pass
        return self._fallback_data().get(credential_id, "")

    def set_password(self, password: str, credential_id: str = "default") -> None:
        if keyring:
            try:
                keyring.set_password(self.service, credential_id, password)
                return
            except Exception:
                pass
        data = self._fallback_data()
        data[credential_id] = password
        self._write_fallback(data)

    def delete_password(self, credential_id: str = "default") -> None:
        if keyring:
            try:
                keyring.delete_password(self.service, credential_id)
            except Exception:
                pass
        data = self._fallback_data()
        data.pop(credential_id, None)
        self._write_fallback(data)

    def _fernet(self) -> Fernet:
        FALLBACK_DIR.mkdir(exist_ok=True)
        if not KEY_PATH.exists():
            KEY_PATH.write_bytes(Fernet.generate_key())
            os.chmod(KEY_PATH, 0o600)
        return Fernet(KEY_PATH.read_bytes())

    def _fallback_data(self) -> dict[str, str]:
        if not SECRETS_PATH.exists():
            return {}
        raw = self._fernet().decrypt(SECRETS_PATH.read_bytes())
        return json.loads(raw.decode("utf-8"))

    def _write_fallback(self, data: dict[str, str]) -> None:
        FALLBACK_DIR.mkdir(exist_ok=True)
        SECRETS_PATH.write_bytes(self._fernet().encrypt(json.dumps(data).encode("utf-8")))
        os.chmod(SECRETS_PATH, 0o600)
