# LinkPilot

LinkPilot is a desktop browser automation app powered by local Ollama vision models and Playwright.

## Installation

Install Python 3.11 or newer, then open `LinkPilot.app` on macOS or `LinkPilot.exe` on Windows.

## First Launch

The Setup tab checks Python packages, Ollama, the Ollama server, Playwright Chromium, and the selected model. Missing components can be repaired from Setup or Diagnostics.

## API Setup

Open Settings, enter API base URL, username, password, worker ID, and location. Passwords are stored in Keychain, Windows Credential Manager, or encrypted fallback storage.

## Models

Use Models to refresh installed Ollama models, download a model, delete one, or set the active model.

## Troubleshooting

Use Diagnostics and Release tabs to repair components and export diagnostics. Logs are stored in `logs/` and rotated automatically.

## Building

Development:

```bash
.venv/bin/python app.py
```

macOS:

```bash
./build/build_mac.sh
```

Windows:

```bat
build\build_windows.bat
```
