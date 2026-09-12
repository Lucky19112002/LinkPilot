from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec

from config import Config, load_config, save_config
from ollama_manager import OllamaManager, ollama_executable, start_detached


REQUIRED_PACKAGES = ("PySide6", "playwright", "requests", "keyring", "cryptography", "psutil", "PIL", "imageio")


def _run_logged(command: list[str], log=lambda message: None) -> int:
    log("Running: " + " ".join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert process.stdout is not None
    for line in process.stdout:
        line = line.strip()
        if line:
            log(line)
    return process.wait()


def _playwright_command(*args: str) -> list[str]:
    try:
        from playwright._impl._driver import compute_driver_executable

        node, cli = compute_driver_executable()
        return [node, cli, *args]
    except Exception:
        return [sys.executable, "-m", "playwright", *args]


def check_python() -> bool:
    return sys.version_info >= (3, 11)


def in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def install_requirements(log=lambda message: None) -> bool:
    if getattr(sys, "frozen", False):
        return packages_ok()
    return _run_logged([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], log) == 0


def packages_ok() -> bool:
    return all(find_spec(name) for name in REQUIRED_PACKAGES)


def check_ollama() -> bool:
    return ollama_executable() is not None


def install_ollama() -> None:
    webbrowser.open("https://ollama.com/download")


def wait_for_ollama_install(timeout: int = 600) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check_ollama():
            return True
        time.sleep(5)
    return False


def start_ollama() -> None:
    exe = ollama_executable()
    if exe:
        start_detached([exe, "serve"])


def wait_for_ollama_server(config: Config, timeout: int = 60) -> bool:
    manager = OllamaManager(config)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if manager.is_running():
            return True
        time.sleep(1)
    return False


def ensure_ollama_installed(log=lambda message: None) -> bool:
    exe = ollama_executable()
    if exe:
        log(f"Ollama installed: {exe}")
        return True
    log("Ollama missing: opening official download page")
    install_ollama()
    ok = wait_for_ollama_install()
    if ok:
        log(f"Ollama installed: {ollama_executable()}")
    return ok


def ensure_ollama_server(config: Config, log=lambda message: None) -> bool:
    manager = OllamaManager(config)
    if manager.is_running():
        log(f"Ollama server running: {config.ollama_base_url}")
        return True
    log("Ollama server stopped: starting server")
    start_ollama()
    ok = wait_for_ollama_server(config)
    log(f"Ollama server {'ready' if ok else 'failed to start'}: {config.ollama_base_url}")
    return ok


def install_chromium(log=lambda message: None) -> bool:
    return _run_logged(_playwright_command("install", "chromium"), log) == 0


def chromium_ok() -> bool:
    try:
        subprocess.check_call(
            _playwright_command("install", "--dry-run", "chromium"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def verify_internet() -> bool:
    try:
        urllib.request.urlopen("https://ollama.com", timeout=10)
        return True
    except OSError:
        return False


def active_model_ok(config: Config | None = None) -> bool:
    config = config or load_config()
    manager = OllamaManager(config)
    if not manager.is_running():
        return False
    try:
        return config.active_model in manager.list_models()
    except Exception:
        return False


def ensure_active_model(config: Config | None = None, log=lambda message: None) -> bool:
    config = config or load_config()
    manager = OllamaManager(config)
    if not manager.is_running():
        log("Cannot check model until Ollama server is running")
        return False
    try:
        models = manager.list_models()
    except Exception as exc:
        log(f"Model list failed: {exc}")
        return False
    log("Installed models: " + (", ".join(models) if models else "none"))
    if config.active_model in models:
        log(f"Active model configured: {config.active_model}")
        return True
    log(f"Model missing: downloading {config.active_model}")
    if not download_active_model(config, log):
        return False
    try:
        models = manager.list_models()
    except Exception as exc:
        log(f"Model recheck failed: {exc}")
        return False
    ok = config.active_model in models
    log(f"Active model {'configured' if ok else 'still missing'}: {config.active_model}")
    return ok


def download_active_model(config: Config | None = None, log=lambda message: None) -> bool:
    config = config or load_config()
    return _run_logged([ollama_executable() or "ollama", "pull", config.active_model], log) == 0


def complete_first_launch() -> None:
    config = load_config()
    config.first_launch_complete = True
    save_config(config)


def package_versions() -> dict[str, str]:
    names = {"PySide6": "PySide6", "playwright": "playwright", "requests": "requests"}
    out = {}
    for label, package in names.items():
        try:
            out[label] = version(package)
        except PackageNotFoundError:
            out[label] = "missing"
    return out


def verify_environment() -> dict[str, bool]:
    config = load_config()
    manager = OllamaManager(config)
    return {
        "python": check_python(),
        "venv": in_venv(),
        "packages": packages_ok(),
        "ollama": check_ollama(),
        "ollama_server": manager.is_running(),
        "selected_model": active_model_ok(config),
        "chromium": chromium_ok(),
        "internet": verify_internet(),
    }


def run_first_launch(log=lambda message: None, cancel=lambda: False) -> bool:
    config = load_config()
    steps = (
        ("Checking Python", lambda: check_python()),
        ("Checking packages", lambda: packages_ok() or (install_requirements(log) and packages_ok())),
        ("Checking Ollama", lambda: ensure_ollama_installed(log)),
        ("Starting Ollama server", lambda: ensure_ollama_server(config, log)),
        ("Installing Chromium", lambda: chromium_ok() or (install_chromium(log) and chromium_ok())),
        ("Verifying active model", lambda: ensure_active_model(config, log)),
    )
    for label, step in steps:
        if cancel():
            log("Setup cancelled")
            return False
        log(label)
        if not step():
            log(f"{label}: failed")
            return False
        log(f"{label}: OK")
    complete_first_launch()
    log("First launch complete")
    return True
