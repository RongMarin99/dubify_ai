import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.ui.main_window import MainWindow

def test_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    video_path = "C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if os.path.exists(video_path):
        window.video_player.load_video(video_path)

    def capture():
        window.video_player._on_add_blur()
        for _ in range(10):
            QApplication.processEvents()

        pix = window.grab()
        art_path = "C:/Users/RPC/.gemini/antigravity-ide/brain/f8d82df2-0221-451b-9950-3f7716e7d6bc/final_qgraphics_video_blur_verified.png"
        pix.save(art_path)
        print(f"[TEST LOG] Final QGraphicsView MainWindow screenshot saved to: {art_path}")
        app.quit()

    QTimer.singleShot(1500, capture)
    app.exec()

if __name__ == "__main__":
    test_app()
