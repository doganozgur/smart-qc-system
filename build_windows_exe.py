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

    # 2. Generate Synthetic Mock Data (PCB & Door Handles)
    print("Generating mock dataset samples for bundling...")
    pcb_gen = os.path.join(PROJECT_ROOT, "mock_data", "generate_samples.py")
    door_gen = os.path.join(PROJECT_ROOT, "mock_data", "generate_door_handle_samples.py")
    if os.path.exists(pcb_gen):
        subprocess.check_call([sys.executable, pcb_gen], cwd=PROJECT_ROOT)
    if os.path.exists(door_gen):
        subprocess.check_call([sys.executable, door_gen], cwd=PROJECT_ROOT)

    # 3. Clean previous build artifacts
    for d in ["build", "dist"]:
        path = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(path):
            print(f"Cleaning {d}/ directory...")
            shutil.rmtree(path, ignore_errors=True)

    # 4. Execute PyInstaller
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

    # 5. Create RUN.bat launcher helper
    run_bat_path = os.path.join(dist_folder, "RUN.bat")
    with open(run_bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("start \"\" \"%~dp0SmartVisionQC.exe\"\n")
    print(f"Created launcher script: {run_bat_path}")

    # 6. Create ZIP archive for distribution
    zip_output_base = os.path.join(PROJECT_ROOT, "dist", "SmartVisionQC-Windows")
    print(f"Compressing distribution into {zip_output_base}.zip ...")
    shutil.make_archive(zip_output_base, "zip", dist_folder)
    print(f"Zip created at: {zip_output_base}.zip")

    print("=" * 60)
    print("BUILD COMPLETED SUCCESSFULLY!")
    print(f"Output Directory: {dist_folder}")
    print(f"Executable File:  {exe_path}")
    print(f"Zip Archive:      {zip_output_base}.zip")
    print("=" * 60)


if __name__ == "__main__":
    build()
