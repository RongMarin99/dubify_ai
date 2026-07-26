import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

def main():
    # Set high DPI scale factors
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Dubify Studio")
    app.setOrganizationName("Dubify AI")

    # Load QSS Theme
    qss_path = os.path.join(os.path.dirname(__file__), "app", "assets", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    from app.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
