# -*- mode: python ; coding: utf-8 -*-
"""Master PyInstaller Specification for FilterLab.

Produces standalone native bundles:
- macOS: FilterLab.app (with NSMicrophoneUsageDescription & audio document types)
- Windows: dist/FilterLab/FilterLab.exe
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.abspath(os.path.join(spec_dir, ".."))
sys.path.insert(0, project_root)

datas = [
    (os.path.join(project_root, "packaging", "assets"), "assets"),
]
binaries = []
hidden_imports = [
    "scipy.signal",
    "scipy.special",
    "scipy.linalg",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "sounddevice",
    "soundfile",
    "_cffi_backend",
]
hidden_imports += collect_submodules("src")

for pkg_name in ("sounddevice", "_sounddevice_data", "soundfile", "_soundfile_data"):
    try:
        pkg_datas, pkg_bins, pkg_hiddens = collect_all(pkg_name)
        datas += pkg_datas
        binaries += pkg_bins
        hidden_imports += pkg_hiddens
    except Exception:
        pass

rthook_path = os.path.join(project_root, "packaging", "rthook_qt.py")
runtime_hooks = [rthook_path] if os.path.isfile(rthook_path) else []

a = Analysis(
    [os.path.join(project_root, "run.py")],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    icon_file = os.path.join(project_root, "packaging", "assets", "icon.icns")
else:
    icon_file = os.path.join(project_root, "packaging", "assets", "icon.ico")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FilterLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file if os.path.isfile(icon_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FilterLab",
)

if sys.platform == "darwin":
    audio_extensions = ["wav", "aif", "aiff", "flac", "ogg", "mp3", "m4a", "aac", "caf"]
    doc_types = [
        {
            "CFBundleTypeName": f"{ext.upper()} Audio File",
            "CFBundleTypeRole": "Viewer",
            "CFBundleTypeExtensions": [ext],
            "CFBundleTypeIconFile": "icon.icns",
            "LSHandlerRank": "Alternate",
        }
        for ext in audio_extensions
    ]

    info_plist = {
        "CFBundleName": "FilterLab",
        "CFBundleDisplayName": "FilterLab",
        "CFBundleIdentifier": "com.musicaapplicata.filterlab",
        "CFBundleVersion": "1.0.1",
        "CFBundleShortVersionString": "1.0.1",
        "NSHighResolutionCapable": True,
        "NSSupportsAutomaticGraphicsSwitching": True,
        "LSMinimumSystemVersion": "12.0",
        "NSMicrophoneUsageDescription": (
            "FilterLab richiede l'accesso al microfono per analizzare ed elaborare "
            "l'audio live attraverso i filtri digitali del laboratorio."
        ),
        "CFBundleDocumentTypes": doc_types,
        "NSHumanReadableCopyright": "Copyright © 2026 Mario Salvucci — Musica Applicata Suite. MIT License.",
    }

    app = BUNDLE(
        coll,
        name="FilterLab.app",
        icon=icon_file if os.path.isfile(icon_file) else None,
        bundle_identifier="com.musicaapplicata.filterlab",
        info_plist=info_plist,
    )
