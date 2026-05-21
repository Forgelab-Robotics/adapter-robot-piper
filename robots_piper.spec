# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa: F821
# pyright: reportUndefinedVariable=false, reportMissingModuleSource=false
# 在本目录执行：uv run --extra pyinstaller pyinstaller --noconfirm --clean robots_piper.spec
# 或：./scripts/build_pyinstaller.sh

from __future__ import annotations

import os

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_src_dir = os.path.join(_spec_dir, "src")

a = Analysis(
    [os.path.join(_src_dir, "robots_piper", "main.py")],
    pathex=[_src_dir, _spec_dir],
    binaries=[],
    hiddenimports=[
        "robots_piper",
        "robots_piper.config",
        "robots_piper.driver",
        "robots_piper.device_tools",
        "can",
        "can.interface",
        "can.interfaces.socketcan",
        "piper_sdk",
        "typer",
        "click",
        "yaml",
        "pydantic",
        "pydantic_core",
        "pyarrow",
        "numpy",
        "forge_common",
        "forge_msgs",
        "forge_msgs.robot",
        "forge_msgs.value",
        "forge_msgs.utils",
        "forge_robot",
        "forge_robot.node_runner",
        "forge_robot.robot_protocol",
        "dora",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="robots_piper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
