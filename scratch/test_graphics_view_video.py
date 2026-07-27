import sys
import os

from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsItem
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter

class BlurGraphicsItem(QGraphicsItem):
    def __init__(self, w: float = 250.0, h: float = 80.0, parent=None):
        super().__init__(parent)
        self.setZValue(9999.0)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.rect_w: float = max(60.0, w)
        self.rect_h: float = max(30.0, h)

    def boundingRect(self) -> QRectF:
        return QRectF(-20, -25, self.rect_w + 40, self.rect_h + 50)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        blur_rect = QRectF(0, 0, self.rect_w, self.rect_h)
        painter.fillRect(blur_rect, QColor(15, 15, 25, 230))

        grid_pen = QPen(QColor(80, 80, 120, 100), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        step_x = max(10, int(self.rect_w / 12))
        step_y = max(8, int(self.rect_h / 6))
        for x_pos in range(0, int(self.rect_w), step_x):
            painter.drawLine(x_pos, 0, x_pos, int(self.rect_h))
        for y_pos in range(0, int(self.rect_h), step_y):
            painter.drawLine(0, y_pos, int(self.rect_w), y_pos)

        painter.setPen(QPen(QColor("#7d5fff"), 2, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(blur_rect)

        # Handles
        hs = 12
        hs_half = hs / 2.0
        handle_brush = QBrush(QColor("#6c5ce7"))
        handle_pen = QPen(QColor("#ffffff"), 1)
        for hx, hy in [(0, 0), (self.rect_w, 0), (0, self.rect_h), (self.rect_w, self.rect_h)]:
            box = QRectF(hx - hs_half, hy - hs_half, hs, hs)
            painter.fillRect(box, handle_brush)
            painter.setPen(handle_pen)
            painter.drawRect(box)

        mv_rect = QRectF(self.rect_w / 2.0 - 10, -22, 20, 20)
        painter.fillRect(mv_rect, QColor("#6c5ce7"))
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(mv_rect, Qt.AlignCenter, "🤚")

        del_rect = QRectF(self.rect_w + 2, -22, 20, 20)
        painter.fillRect(del_rect, QColor("#e74c3c"))
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(del_rect, Qt.AlignCenter, "✖")

def test_video_graphics_scene():
    app = QApplication(sys.argv)

    scene = QGraphicsScene(0, 0, 800, 600)
    view = QGraphicsView(scene)
    view.resize(800, 600)
    view.show()

    video_item = QGraphicsVideoItem()
    video_item.setSize(QRectF(0, 0, 800, 600).size())
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

    blur = BlurGraphicsItem(250, 80)
    blur.setPos(275, 100)
    scene.addItem(blur)

    def capture():
        pix = view.viewport().grab()
        art_path = "C:/Users/RPC/.gemini/antigravity-ide/brain/f8d82df2-0221-451b-9950-3f7716e7d6bc/graphics_view_video_blur.png"
        pix.save(art_path)
        print(f"[TEST LOG] QGraphicsView Video Blur screenshot saved to: {art_path}")
        app.quit()

    QTimer.singleShot(1500, capture)
    app.exec()

if __name__ == "__main__":
    test_video_graphics_scene()
