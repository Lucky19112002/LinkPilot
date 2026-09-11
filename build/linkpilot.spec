# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata

root = Path.cwd()
icon = root / "assets" / ("logo.icns" if sys.platform == "darwin" else "logo.ico")
icon_arg = str(icon) if icon.exists() else None

a = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "config.json"), "."),
        (str(root / "requirements.txt"), "."),
    ] + copy_metadata("imageio"),
    hiddenimports=["keyring.backends.macOS", "keyring.backends.Windows"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LinkPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_arg,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LinkPilot",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="LinkPilot.app",
        icon=icon_arg,
        bundle_identifier="com.linkpilot.app",
    )
