import sys
import os

# Add translator module directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "translator"))

from app.ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Dubify Studio")
    app.setOrganizationName("Dubify AI")

    icon_path = os.path.join(os.path.dirname(__file__), "translator", "app", "assets", "logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    qss_path = os.path.join(os.path.dirname(__file__), "translator", "app", "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
