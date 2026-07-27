import sys
import os

from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter

def test_graphics_player():
    app = QApplication(sys.argv)

    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.resize(800, 600)
    view.show()

    video_item = QGraphicsVideoItem()
    video_item.setZValue(0)
    scene.addItem(video_item)

    player = QMediaPlayer()
    audio = QAudioOutput()
    player.setAudioOutput(audio)
    player.setVideoOutput(video_item)

    # Add blur graphics item
    class BlurItem(QGraphicsItem):
        def __init__(self, w=250, h=80):
            super().__init__()
            self.setZValue(9999)
            self.setFlags(
                QGraphicsItem.ItemIsMovable |
                QGraphicsItem.ItemIsSelectable |
                QGraphicsItem.ItemSendsGeometryChanges
            )
            self.rect_w = w
            self.rect_h = h

        def boundingRect(self):
            return QRectF(-10, -10, self.rect_w + 20, self.rect_h + 20)

        def paint(self, painter, option, widget=None):
            rect = QRectF(0, 0, self.rect_w, self.rect_h)
            painter.fillRect(rect, QColor(15, 15, 25, 220))
            painter.setPen(QPen(QColor("#7d5fff"), 2))
            painter.drawRect(rect)

    blur = BlurItem()
    blur.setPos(200, 200)
    scene.addItem(blur)

    print(f"[TEST LOG] QGraphicsScene test OK, scene items count: {len(scene.items())}, blur zValue: {blur.zValue()}")

if __name__ == "__main__":
    test_graphics_player()
