from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import bootstrap
import service
from config import Config, load_config, save_config
import updater as updater_module
from updater import Updater


def test_first_launch_flag_roundtrip() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        cfg = Config(first_launch_complete=False)
        save_config(cfg, path)
        loaded = load_config(path)
        loaded.first_launch_complete = True
        save_config(loaded, path)
        assert load_config(path).first_launch_complete is True


def test_verify_environment_keys() -> None:
    keys = set(bootstrap.verify_environment())
    assert {"python", "venv", "packages", "ollama", "ollama_server", "selected_model", "chromium", "internet"} <= keys


def test_first_launch_starts_server_before_model_check(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(bootstrap, "load_config", lambda: Config())
    monkeypatch.setattr(bootstrap, "check_python", lambda: True)
    monkeypatch.setattr(bootstrap, "packages_ok", lambda: True)
    monkeypatch.setattr(bootstrap, "ensure_ollama_installed", lambda log: calls.append("installed") or True)
    monkeypatch.setattr(bootstrap, "ensure_ollama_server", lambda config, log: calls.append("server") or True)
    monkeypatch.setattr(bootstrap, "chromium_ok", lambda: True)
    monkeypatch.setattr(bootstrap, "ensure_active_model", lambda config, log: calls.append("model") or True)
    monkeypatch.setattr(bootstrap, "complete_first_launch", lambda: calls.append("complete"))

    assert bootstrap.run_first_launch()
    assert calls == ["installed", "server", "model", "complete"]


def test_launch_agent_path(monkeypatch) -> None:
    if sys.platform != "darwin":
        return
    with TemporaryDirectory() as tmp:
        monkeypatch.setattr(Path, "home", lambda: Path(tmp))
        path = service.set_launch_on_login(True)
        assert path.name == "com.linkpilot.worker.plist"
        assert path.exists()
        service.set_launch_on_login(False)
        assert not path.exists()


def test_export_data_has_no_password() -> None:
    data = Config(api_username="lucky", credential_id="default").__dict__.copy()
    data.pop("profile", None)
    text = json.dumps(data)
    assert "api_password" not in text
    assert "password" not in text


def test_update_staging_and_apply() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        updater_module.PENDING = root / "pending.json"
        source = root / "source"
        source.mkdir()
        (source / "new.txt").write_text("new", encoding="utf-8")
        archive = root / "update.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(source / "new.txt", "new.txt")
        app = root / "app"
        app.mkdir()
        updater = Updater()
        staged = updater.stage_download(archive.as_uri(), root / "staged")
        assert staged.exists()
        assert updater.apply_pending(app)
        assert (app / "new.txt").read_text(encoding="utf-8") == "new"
