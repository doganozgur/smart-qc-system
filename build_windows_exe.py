"""
Automated Build Script for Compiling SmartVisionQC into a Windows Standalone .exe.
Usage on Windows:
    python build_windows_exe.py
"""

import os
import sys
import subprocess
import shutil

# Force UTF-8 encoding on standard output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def build():
    print("=" * 60)
    print("  SmartVisionQC Windows .EXE Build Tool")
    print("=" * 60)

    # 1. Check PyInstaller
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Clean previous build artifacts
    for d in ["build", "dist"]:
        path = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(path):
            print(f"Cleaning {d}/ directory...")
            shutil.rmtree(path, ignore_errors=True)

    # 3. Execute PyInstaller
    spec_path = os.path.join(PROJECT_ROOT, "SmartVisionQC.spec")
    print(f"Building .EXE with PyInstaller ({spec_path})...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        spec_path
    ]
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)

    dist_folder = os.path.join(PROJECT_ROOT, "dist", "SmartVisionQC")
    exe_path = os.path.join(dist_folder, "SmartVisionQC.exe")
    print("=" * 60)
    print("BUILD COMPLETED SUCCESSFULLY!")
    print(f"Output Directory: {dist_folder}")
    print(f"Executable File: {exe_path}")
    print("=" * 60)


if __name__ == "__main__":
    build()
