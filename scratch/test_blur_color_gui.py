import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtCore import Qt, QRectF, QTimer
from app.ui.overlay_canvas import VideoOverlayCanvas

def test_blur_color():
    app = QApplication(sys.argv)

    scene = QGraphicsScene(0, 0, 985, 426)
    view = QGraphicsView(scene)
    view.setStyleSheet("background-color: #0b0a14; border: none;")
    view.resize(985, 426)
    view.show()

    video_item = QGraphicsVideoItem()
    video_item.setSize(QRectF(0, 0, 985, 426).size())
    video_item.setZValue(0)
    scene.addItem(video_item)

    player = QMediaPlayer()
    audio = QAudioOutput()
    player.setAudioOutput(audio)
    player.setVideoOutput(video_item)

    video_path = "C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if os.path.exists(video_path):
        player.setSource(video_path)
        player.play()

    overlay_canvas = VideoOverlayCanvas()
    overlay_canvas.resize(985, 426)
    overlay_canvas.blur_x_pct = 0.35
    overlay_canvas.blur_y_pct = 0.15
    overlay_canvas.blur_w_pct = 0.30
    overlay_canvas.blur_h_pct = 0.18
    overlay_canvas.set_blur_color("#6c5ce7", 0.65)  # Purple semi-transparent blur tint
    overlay_canvas.add_blur_region()

    proxy = scene.addWidget(overlay_canvas)
    proxy.setZValue(9999)

    def capture():
        pix = view.viewport().grab()
        art_path = "C:/Users/RPC/.gemini/antigravity-ide/brain/f8d82df2-0221-451b-9950-3f7716e7d6bc/custom_blur_color_transparent.png"
        pix.save(art_path)
        print(f"[TEST LOG] Custom Blur Color & Transparency screenshot saved to: {art_path}")
        app.quit()

    QTimer.singleShot(1500, capture)
    app.exec()

if __name__ == "__main__":
    test_blur_color()
