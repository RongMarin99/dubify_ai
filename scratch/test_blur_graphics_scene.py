import sys
import os

from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter

class BlurGraphicsItem(QGraphicsItem):
    def __init__(self, w: float = 250.0, h: float = 80.0, parent=None):
        super().__init__(parent)
        self.setZValue(9999.0)  # Highest Z-Order (ALWAYS above video layer)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        
        self.rect_w: float = max(60.0, w)
        self.rect_h: float = max(30.0, h)
        
        self._resizing_corner: str = ""
        self._drag_start_scene_pos: QPointF = QPointF()
        self._start_rect_w: float = self.rect_w
        self._start_rect_h: float = self.rect_h
        self._start_pos: QPointF = QPointF()

    def boundingRect(self) -> QRectF:
        return QRectF(-20, -25, self.rect_w + 40, self.rect_h + 50)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. Frosted Glass Pixelated Blur Grid Texture
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

        # 2. Selection Border
        border_pen = QPen(QColor("#7d5fff"), 2, Qt.SolidLine if self.isSelected() else Qt.DashLine)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(blur_rect)

        # 3. Four Corner Resize Handles (TL, TR, BL, BR)
        handle_size = 12
        hs_half = handle_size / 2.0
        
        # Top-Left (TL)
        tl_rect = QRectF(-hs_half, -hs_half, handle_size, handle_size)
        painter.fillRect(tl_rect, QColor("#6c5ce7"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawRect(tl_rect)

        # Top-Right (TR)
        tr_rect = QRectF(self.rect_w - hs_half, -hs_half, handle_size, handle_size)
        painter.fillRect(tr_rect, QColor("#6c5ce7"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawRect(tr_rect)

        # Bottom-Left (BL)
        bl_rect = QRectF(-hs_half, self.rect_h - hs_half, handle_size, handle_size)
        painter.fillRect(bl_rect, QColor("#6c5ce7"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawRect(bl_rect)

        # Bottom-Right (BR)
        br_rect = QRectF(self.rect_w - hs_half, self.rect_h - hs_half, handle_size, handle_size)
        painter.fillRect(br_rect, QColor("#6c5ce7"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawRect(br_rect)

        # 4. Delete (✖) Button at Top-Right
        del_rect = QRectF(self.rect_w - 10, -22, 22, 22)
        painter.fillRect(del_rect, QColor("#e74c3c"))
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(del_rect, Qt.AlignCenter, "✖")

    def mousePressEvent(self, event):
        pos = event.pos()
        del_rect = QRectF(self.rect_w - 10, -22, 22, 22)
        if del_rect.contains(pos):
            print("[DEBUG LOG] Blur object deleted via ✖ button")
            if self.scene():
                self.scene().removeItem(self)
            return

        handle_size = 14
        hs_half = handle_size / 2.0
        tl_rect = QRectF(-hs_half, -hs_half, handle_size, handle_size)
        tr_rect = QRectF(self.rect_w - hs_half, -hs_half, handle_size, handle_size)
        bl_rect = QRectF(-hs_half, self.rect_h - hs_half, handle_size, handle_size)
        br_rect = QRectF(self.rect_w - hs_half, self.rect_h - hs_half, handle_size, handle_size)

        if tl_rect.contains(pos):
            self._resizing_corner = "tl"
        elif tr_rect.contains(pos):
            self._resizing_corner = "tr"
        elif bl_rect.contains(pos):
            self._resizing_corner = "bl"
        elif br_rect.contains(pos):
            self._resizing_corner = "br"
        else:
            self._resizing_corner = ""

        if self._resizing_corner:
            self._drag_start_scene_pos = event.scenePos()
            self._start_rect_w = self.rect_w
            self._start_rect_h = self.rect_h
            self._start_pos = self.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing_corner:
            delta = event.scenePos() - self._drag_start_scene_pos
            dx, dy = delta.x(), delta.y()

            if self._resizing_corner == "br":
                self.rect_w = max(50.0, self._start_rect_w + dx)
                self.rect_h = max(20.0, self._start_rect_h + dy)
            elif self._resizing_corner == "bl":
                new_w = max(50.0, self._start_rect_w - dx)
                self.rect_h = max(20.0, self._start_rect_h + dy)
                self.setPos(self._start_pos.x() + (self._start_rect_w - new_w), self.pos().y())
                self.rect_w = new_w
            elif self._resizing_corner == "tr":
                new_h = max(20.0, self._start_rect_h - dy)
                self.rect_w = max(50.0, self._start_rect_w + dx)
                self.setPos(self.pos().x(), self._start_pos.y() + (self._start_rect_h - new_h))
                self.rect_h = new_h
            elif self._resizing_corner == "tl":
                new_w = max(50.0, self._start_rect_w - dx)
                new_h = max(20.0, self._start_rect_h - dy)
                self.setPos(self._start_pos.x() + (self._start_rect_w - new_w), self._start_pos.y() + (self._start_rect_h - new_h))
                self.rect_w = new_w
                self.rect_h = new_h

            self.prepareGeometryChange()
            self.update()
            if self.scene():
                self.scene().update()
        else:
            super().mouseMoveEvent(event)
            if self.scene():
                self.scene().update()

    def mouseReleaseEvent(self, event):
        self._resizing_corner = ""
        super().mouseReleaseEvent(event)

def test_blur_item():
    app = QApplication(sys.argv)
    scene = QGraphicsScene(0, 0, 800, 600)
    view = QGraphicsView(scene)
    view.resize(800, 600)
    view.show()

    blur = BlurGraphicsItem(250, 80)
    blur.setPos(275, 200)
    blur.setSelected(True)
    scene.addItem(blur)

    print(f"[DEBUG LOG] Blur object created | pos={blur.pos()} | size=({blur.rect_w}x{blur.rect_h}) | scene_added=True | zValue={blur.zValue()} | visible={blur.isVisible()}")
    print("[TEST LOG] BlurGraphicsItem test SUCCESS")

if __name__ == "__main__":
    test_blur_item()
