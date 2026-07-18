# -*- mode: python ; coding: utf-8 -*-
#
# Reproducible PyInstaller build config -- committed, not auto-generated.
# Build with: .venv\Scripts\python.exe -m PyInstaller arc_companion.spec
#
# --onedir, not --onefile: customtkinter ships its own data files (.json
# theme files, .otf fonts) that PyInstaller doesn't auto-include, and its
# own packaging docs specifically say onefile mode doesn't work here. Output
# is a folder (dist/ArcRaidersBlueprintGoblin/) to share, not a single .exe --
# the .exe inside it still needs the rest of that folder alongside it.

from pathlib import Path

import customtkinter

customtkinter_dir = Path(customtkinter.__file__).parent

a = Analysis(
    ["main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("data", "data"),
        (str(customtkinter_dir), "customtkinter"),
    ],
    hiddenimports=[],
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
    name="ArcRaidersBlueprintGoblin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ArcRaidersBlueprintGoblin",
)
