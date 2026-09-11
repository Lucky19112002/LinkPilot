from __future__ import annotations

import os
import sys
from pathlib import Path

from paths import app_dir

APP_DIR = app_dir()


def set_launch_on_login(enabled: bool) -> Path:
    if sys.platform == "darwin":
        path = Path.home() / "Library/LaunchAgents/com.linkpilot.worker.plist"
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            if getattr(sys, "frozen", False):
                args = f"<string>{sys.executable}</string>"
            else:
                args = f"<string>{APP_DIR / '.venv/bin/python'}</string><string>{APP_DIR / 'app.py'}</string>"
            path.write_text(
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.linkpilot.worker</string>
<key>ProgramArguments</key><array>{args}</array>
<key>WorkingDirectory</key><string>{APP_DIR}</string>
<key>RunAtLoad</key><true/>
</dict></plist>
""",
                encoding="utf-8",
            )
        elif path.exists():
            path.unlink()
        return path
    if sys.platform == "win32":
        startup = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup"
        path = startup / "LinkPilot.cmd"
        if enabled:
            startup.mkdir(parents=True, exist_ok=True)
            command = f'"{sys.executable}"\r\n' if getattr(sys, "frozen", False) else f'cd /d "{APP_DIR}"\r\n.venv\\Scripts\\python.exe app.py\r\n'
            path.write_text(command, encoding="utf-8")
        elif path.exists():
            path.unlink()
        return path
    raise RuntimeError("Launch on login is supported on macOS and Windows")
