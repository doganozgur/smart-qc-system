"""
Automated Build Script for Compiling SmartVisionQC into a Windows Standalone .exe.
Usage on Windows:
    python build_windows_exe.py
"""

import os
import sys
import subprocess
import shutil

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def build():
    print("=" * 60)
    print("  SmartVisionQC Windows .EXE Derleme Aracı")
    print("=" * 60)

    # 1. Check PyInstaller
    try:
        import PyInstaller
        print(f"✔ PyInstaller kurulu (Versiyon: {PyInstaller.__version__})")
    except ImportError:
        print("⚡ PyInstaller kuruluyor...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Clean previous build artifacts
    for d in ["build", "dist"]:
        path = os.path.join(PROJECT_ROOT, d)
        if os.path.exists(path):
            print(f"🧹 Eski {d}/ klasörü temizleniyor...")
            shutil.rmtree(path, ignore_errors=True)

    # 3. Execute PyInstaller
    spec_path = os.path.join(PROJECT_ROOT, "SmartVisionQC.spec")
    print(f"🚀 PyInstaller ile .EXE oluşturuluyor ({spec_path})...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        spec_path
    ]
    subprocess.check_call(cmd, cwd=PROJECT_ROOT)

    dist_folder = os.path.join(PROJECT_ROOT, "dist", "SmartVisionQC")
    exe_path = os.path.join(dist_folder, "SmartVisionQC.exe")
    print("=" * 60)
    print("🎉 DERLEME BAŞARIYLA TAMAMLANDI!")
    print(f"📂 Çıktı Klasörü: {dist_folder}")
    print(f"🖥 Çalıştırılabilir Dosya: {exe_path}")
    print("=" * 60)


if __name__ == "__main__":
    build()
