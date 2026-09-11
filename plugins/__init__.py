from __future__ import annotations

import importlib
import pkgutil


HOOKS = ("before_navigation", "after_navigation", "before_llm", "after_action", "on_success")


class PluginManager:
    def __init__(self):
        self.plugins = []
        for module in pkgutil.iter_modules(__path__):
            if module.name.startswith("_"):
                continue
            self.plugins.append(importlib.import_module(f"{__name__}.{module.name}"))

    def call(self, hook: str, **kwargs) -> None:
        if hook not in HOOKS:
            return
        for plugin in self.plugins:
            func = getattr(plugin, hook, None)
            if func:
                func(**kwargs)
