import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.ui.main_window import MainWindow

def test_live_video_blur():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    video_path = "C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if os.path.exists(video_path):
        window.video_player.load_video(video_path)

    def capture_screenshot():
        try:
            print("[TEST LOG] Calling window._on_add_blur()...")
            window._on_add_blur()
            QApplication.processEvents()

            pix = window.grab()
            os.makedirs("scratch", exist_ok=True)
            shot_path = os.path.abspath("scratch/video_blur_live_result.png")
            pix.save(shot_path)

            art_dir = "C:/Users/RPC/.gemini/antigravity-ide/brain/f8d82df2-0221-451b-9950-3f7716e7d6bc"
            if os.path.exists(art_dir):
                art_path = os.path.join(art_dir, "live_blur_window_result.png")
                pix.save(art_path)
                print(f"[TEST LOG] Saved artifact screenshot to: {art_path}")

            print(f"[TEST LOG] Live window screenshot saved to: {shot_path}")
        except Exception as e:
            traceback.print_exc()
        finally:
            app.quit()

    QTimer.singleShot(1000, capture_screenshot)
    app.exec()

if __name__ == "__main__":
    test_live_video_blur()
