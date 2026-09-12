from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
import ssl
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

from version import VERSION
STAGING = Path("updates/staged")
PENDING = Path("updates/pending.json")


def semver(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


class Updater:
    def __init__(self, update_url: str = "", allow_insecure_https: bool = False):
        self.update_url = update_url
        self.allow_insecure_https = allow_insecure_https

    def check(self) -> dict:
        if not self.update_url:
            return {"status": "disabled", "version": VERSION}
        try:
            context = ssl._create_unverified_context() if self.allow_insecure_https else ssl.create_default_context()
            with urlopen(self.update_url, timeout=10, context=context) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"status": "unavailable", "version": VERSION, "error": str(exc)}
        latest = str(payload.get("version") or payload.get("tag_name") or "")
        return {
            "status": "available" if semver(latest) > semver(VERSION) else "current",
            "version": VERSION,
            "latest": latest,
            "download_url": payload.get("download_url") or payload.get("html_url", ""),
            "sha256": payload.get("sha256", ""),
        }

    def stage_download(self, url: str, target: Path = STAGING, checksum: str = "", progress=lambda done, total: None, cancel=lambda: False) -> Path:
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        path = target / (Path(url.split("?")[0]).name or "update.bin")
        context = ssl._create_unverified_context() if self.allow_insecure_https else ssl.create_default_context()
        with urlopen(url, timeout=60, context=context) as response:
            total = int(response.headers.get("content-length", 0))
            done = 0
            with path.open("wb") as file:
                while chunk := response.read(1024 * 512):
                    if cancel():
                        raise RuntimeError("Update cancelled")
                    file.write(chunk)
                    done += len(chunk)
                    progress(done, total)
        if checksum and self.file_sha256(path) != checksum.lower():
            raise RuntimeError("Checksum verification failed")
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                archive.extractall(target / "payload")
        PENDING.parent.mkdir(exist_ok=True)
        PENDING.write_text(json.dumps({"path": str(target.resolve()), "archive": str(path.resolve())}, indent=2), encoding="utf-8")
        return path

    def apply_pending(self, app_dir: Path | None = None) -> bool:
        if not PENDING.exists():
            return False
        app_dir = app_dir or Path(__file__).resolve().parent
        data = json.loads(PENDING.read_text(encoding="utf-8"))
        staging = Path(data["path"])
        source = staging / "payload" if (staging / "payload").exists() else staging
        backup = app_dir.with_name(app_dir.name + ".backup")
        if backup.exists():
            shutil.rmtree(backup)
        ignore = shutil.ignore_patterns(".venv", "logs", "updates", "config.json")
        shutil.copytree(app_dir, backup, ignore=ignore)
        try:
            for item in source.iterdir():
                target = app_dir / item.name
                if item.name in {".venv", "logs", "updates", "config.json"}:
                    continue
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            PENDING.unlink()
            return True
        except Exception:
            for item in backup.iterdir():
                target = app_dir / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            raise

    def restart(self) -> None:
        subprocess.Popen([sys.executable, "app.py"])
        raise SystemExit(0)

    def file_sha256(self, path: Path) -> str:
        digest = sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
