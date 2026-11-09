"""
Main Desktop Application Launcher for Vision QC System.
"""

import sys
import os

# Fix GNOME / GLib gsettings schema crash on Ubuntu
os.environ.setdefault("QT_QPA_PLATFORMTHEME", "generic")

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
