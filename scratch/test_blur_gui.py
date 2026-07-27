import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.ui.main_window import MainWindow

def test_gui_blur():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    # Load video if available
    video_path = "C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if os.path.exists(video_path):
        window.video_player.load_video(video_path)

    # Process events to render UI layout
    QApplication.processEvents()

    # Programmatically trigger Add Blur
    print("[TEST LOG] Triggering _on_add_blur()...")
    window.video_player._on_add_blur()
    QApplication.processEvents()

    print(f"[TEST LOG] blur_enabled: {window.video_player.overlay_canvas.blur_enabled}")
    print(f"[TEST LOG] overlay_canvas geometry: {window.video_player.overlay_canvas.geometry()}")
    print(f"[TEST LOG] video_container geometry: {window.video_player.video_container.geometry()}")

    # Take screenshot of video container
    pix = window.video_player.video_container.grab()
    os.makedirs("scratch", exist_ok=True)
    shot_path = os.path.abspath("scratch/blur_test_screenshot.png")
    pix.save(shot_path)
    print(f"[TEST LOG] Screenshot saved to: {shot_path}")

if __name__ == "__main__":
    test_gui_blur()
