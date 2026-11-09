# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification file for SmartVisionQC Desktop Application.
Bundles PySide6, OpenCV, SQLite, SciPy, Scikit-learn, and application data into a standalone Windows .exe.
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
PROJECT_ROOT = os.path.abspath(SPECPATH)

added_files = [
    (os.path.join(PROJECT_ROOT, 'mock_data'), 'mock_data'),
    (os.path.join(PROJECT_ROOT, 'data'), 'data'),
]

# Collect PySide6 plugins and data files
try:
    added_files += collect_data_files('PySide6', include_py_files=False)
except Exception:
    pass

hidden_imports = [
    'core',
    'core.locator',
    'core.door_handle_locator',
    'core.door_handle_inspector',
    'core.golden_reference',
    'core.pipeline',
    'core.active_learner',
    'core.database',
    'client',
    'client.network_client',
    'client.ui',
    'client.ui.main_window',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'cv2',
    'numpy',
    'scipy',
    'scipy.ndimage',
    'scipy.spatial',
    'sklearn',
    'sklearn.utils',
    'PIL',
    'PIL.Image',
    'sqlite3',
    'requests',
]

try:
    hidden_imports += collect_submodules('core')
except Exception:
    pass

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'client', 'app.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SmartVisionQC',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SmartVisionQC',
)
