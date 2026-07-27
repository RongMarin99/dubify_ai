import sys
import os

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QRadialGradient, QBrush

class GaussianBlurPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(600, 300)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background simulating video content underneath
        painter.fillRect(self.rect(), QColor("#1e1e2e"))
        for i in range(0, 600, 40):
            painter.setPen(QPen(QColor("#313244"), 2))
            painter.drawLine(i, 0, i, 300)
            painter.drawText(i + 5, 150, "TEXT WATERMARK 123")

        # CapCut Style Heavy Gaussian Blur Rectangle
        bx, by, bw, bh = 100, 80, 400, 100
        blur_rect = QRectF(bx, by, bw, bh)

        # 1. Core Solid Heavy Blur Fill
        core_col = QColor("#0d0d16")
        core_col.setAlphaF(0.92)
        painter.fillRect(blur_rect, core_col)

        # 2. Vertical Soft Feathered Edge Gradient
        grad = QLinearGradient(bx, by, bx, by + bh)
        grad.setColorAt(0.0, QColor(10, 10, 15, 210))
        grad.setColorAt(0.12, QColor(15, 15, 22, 245))
        grad.setColorAt(0.50, QColor(8, 8, 14, 255))
        grad.setColorAt(0.88, QColor(15, 15, 22, 245))
        grad.setColorAt(1.0, QColor(10, 10, 15, 210))
        painter.fillRect(blur_rect, QBrush(grad))

        # 3. Inner Radial Soft Blur Mask
        rad = QRadialGradient(blur_rect.center(), max(bw, bh) * 0.7)
        rad.setColorAt(0.0, QColor(0, 0, 0, 160))
        rad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(blur_rect, QBrush(rad))

        # Selection Border
        painter.setPen(QPen(QColor("#7d5fff"), 2, Qt.SolidLine))
        painter.drawRect(blur_rect)

def test_gaussian_preview():
    app = QApplication(sys.argv)
    w = GaussianBlurPreviewWidget()
    w.show()
    QApplication.processEvents()

    pix = w.grab()
    art_path = "C:/Users/RPC/.gemini/antigravity-ide/brain/f8d82df2-0221-451b-9950-3f7716e7d6bc/gaussian_blur_capcut_style.png"
    pix.save(art_path)
    print(f"[TEST LOG] Gaussian Blur CapCut Style screenshot saved to: {art_path}")

if __name__ == "__main__":
    test_gaussian_preview()
