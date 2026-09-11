# LinkPilot Developer Guide

Use Python 3.12 in a virtual environment.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/
```

Build scripts live in `build/`. Release metadata lives in `version.py`. Do not duplicate version constants.

Plugins can implement hooks in `plugins/`: `before_navigation`, `after_navigation`, `before_llm`, `after_action`, and `on_success`.
