"""
Main Desktop Application Launcher for Vision QC System.
Supports both direct Python execution and PyInstaller Windows .exe bundle.
Includes robust path resolution and crash logging for Windows deployment.
"""

import sys
import os
import traceback

# Fix GNOME / GLib gsettings schema crash on Ubuntu
os.environ.setdefault("QT_QPA_PLATFORMTHEME", "generic")


def get_app_dir() -> str:
    """Returns the base project directory both in development and when frozen by PyInstaller."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller executable
        return os.path.dirname(os.path.abspath(sys.executable))
    # Running from source
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PROJECT_ROOT = get_app_dir()

# Ensure project root is in sys.path
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# If running as PyInstaller bundle with _MEIPASS, ensure it is also in sys.path
if hasattr(sys, "_MEIPASS") and sys._MEIPASS not in sys.path:
    sys.path.insert(0, sys._MEIPASS)


def exception_hook(exctype, value, tb):
    """Global exception hook to prevent silent crashes on Windows."""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    log_path = os.path.join(get_app_dir(), "crash_log.txt")

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(error_msg)
    except Exception:
        pass

    # Windows message box
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"SmartVisionQC baslatilirken bir hata olustu:\n\n{value}\n\nDetaylar '{log_path}' dosyasina kaydedildi.",
            "SmartVisionQC - Hata Raporu",
            0x10  # MB_ICONERROR
        )
    except Exception:
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Hata", f"Uygulama hatasi:\n{value}\n\n{error_msg}")
        except Exception:
            sys.__stderr__.write(error_msg)

    sys.exit(1)


sys.excepthook = exception_hook

from PySide6.QtWidgets import QApplication
from client.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SmartVisionQC")

    window = MainWindow(project_dir=PROJECT_ROOT)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
