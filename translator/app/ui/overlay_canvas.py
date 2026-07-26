import os
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QBrush, QImage, QDragEnterEvent, QDropEvent

class VideoOverlayCanvas(QWidget):
    subtitle_pos_changed = Signal(float, float)  # x_pct, y_pct
    logo_changed = Signal(str, float, float, float, float, bool)  # path, x, y, w, h, enabled
    blur_changed = Signal(float, float, float, float, bool)       # x, y, w, h, enabled
    upload_clicked = Signal()
    video_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self.video_has_loaded: bool = False

        # Active Subtitle Text & Relative Position (0.0 to 1.0)
        self.sub_text: str = ""
        self.sub_x_pct: float = 0.5   # Center horizontally by default
        self.sub_y_pct: float = 0.85  # Bottom by default
        self.sub_font_family: str = "Khmer OS Battambang"
        self.sub_font_size: int = 24
        self.sub_primary_color: str = "#FFFFFF"
        self.sub_outline_color: str = "#000000"

        # Logo / Watermark Properties
        self.logo_path: str = ""
        self.logo_pixmap: Optional[QPixmap] = None
        self.logo_enabled: bool = False
        self.logo_x_pct: float = 0.05
        self.logo_y_pct: float = 0.05
        self.logo_w_pct: float = 0.20
        self.logo_h_pct: float = 0.12

        # Blur Mask Box Properties
        self.blur_enabled: bool = False
        self.blur_x_pct: float = 0.10
        self.blur_y_pct: float = 0.80
        self.blur_w_pct: float = 0.80
        self.blur_h_pct: float = 0.12

        # Interaction Drag State
        self._dragging_target: Optional[str] = None  # "sub", "logo", "logo_resize", "blur", "blur_resize"
        self._drag_start_pos: QPointF = QPointF()
        self._element_start_rect: QRectF = QRectF()

    def set_video_loaded(self, loaded: bool):
        self.video_has_loaded = loaded
        self.update()

    def set_subtitle_text(self, text: str):
        self.sub_text = text
        self.update()

    def set_subtitle_style(self, font_family: str, font_size: int, primary_color: str, outline_color: str):
        self.sub_font_family = font_family
        self.sub_font_size = font_size
        self.sub_primary_color = primary_color
        self.sub_outline_color = outline_color
        self.update()

    def load_logo(self, image_path: str):
        if os.path.exists(image_path):
            self.logo_path = image_path
            self.logo_pixmap = QPixmap(image_path)
            self.logo_enabled = True
            self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, True)
            self.update()

    def set_blur_enabled(self, enabled: bool):
        self.blur_enabled = enabled
        self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, enabled)
        self.update()

    def add_blur_region(self):
        """Create a new interactive Blur Box in the center of the video preview."""
        self.blur_x_pct = 0.25
        self.blur_y_pct = 0.35
        self.blur_w_pct = 0.50
        self.blur_h_pct = 0.20
        self.set_blur_enabled(True)
        self.raise_()
        self.update()

    def add_subtitle_object(self, text: str = ""):
        """Create a new interactive Subtitle object at bottom center of video preview."""
        self.sub_x_pct = 0.50
        self.sub_y_pct = 0.85
        if text:
            self.sub_text = text
        elif not self.sub_text:
            self.sub_text = "សូមស្វាគមន៍មកកាន់ Dubify Studio"
        self.raise_()
        self.update()

    def auto_blur_chinese_subtitles(self):
        self.blur_x_pct = 0.08
        self.blur_y_pct = 0.80
        self.blur_w_pct = 0.84
        self.blur_h_pct = 0.12
        self.set_blur_enabled(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                self.video_dropped.emit(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        H = self.height()

        if W <= 0 or H <= 0:
            return

        # Render Center Upload Card if no video is loaded
        if not self.video_has_loaded:
            cw, ch = 340, 150
            cx = (W - cw) / 2.0
            cy = (H - ch) / 2.0
            card_rect = QRectF(cx, cy, cw, ch)

            # Card background
            painter.fillRect(card_rect, QColor("#1c1a33"))
            painter.setPen(QPen(QColor("#6c5ce7"), 2, Qt.DashLine))
            painter.drawRoundedRect(card_rect, 10, 10)

            # Icon
            painter.setFont(QFont("Segoe UI", 28))
            painter.setPen(QColor("#a29bfe"))
            painter.drawText(QRectF(cx, cy + 15, cw, 45), Qt.AlignCenter, "📁")

            # Title
            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(cx, cy + 65, cw, 25), Qt.AlignCenter, "Click to Upload Video")

            # Subtitle hint
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor("#8c89b4"))
            painter.drawText(QRectF(cx, cy + 95, cw, 35), Qt.AlignCenter, "or Drag & Drop MP4 / MKV / AVI here")

        # 1. Render CapCut-Style Blur Box Mask (if enabled)
        if self.video_has_loaded and self.blur_enabled:
            bx = self.blur_x_pct * W
            by = self.blur_y_pct * H
            bw = self.blur_w_pct * W
            bh = self.blur_h_pct * H
            blur_rect = QRectF(bx, by, bw, bh)

            # Translucent frosted blur mask preview area
            painter.fillRect(blur_rect, QColor(80, 80, 110, 85))
            painter.setPen(QPen(QColor("#7d5fff"), 1.5, Qt.SolidLine))
            painter.drawRect(blur_rect)

            # Top-Left Drag Handle (🤚 Move)
            tl_rect = QRectF(bx - 10, by - 10, 20, 20)
            painter.fillRect(tl_rect, QColor("#6c5ce7"))
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(tl_rect, Qt.AlignCenter, "🤚")

            # Top-Right Close Button (✖ Remove Blur)
            tr_rect = QRectF(bx + bw - 10, by - 10, 20, 20)
            painter.fillRect(tr_rect, QColor("#e74c3c"))
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(tr_rect, Qt.AlignCenter, "✖")

            # Bottom-Right Resize Handle (◢ Crop & Resize)
            br_rect = QRectF(bx + bw - 10, by + bh - 10, 20, 20)
            painter.fillRect(br_rect, QColor("#6c5ce7"))
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(br_rect, Qt.AlignCenter, "◢")

        # 2. Render Logo / Watermark Overlay (if enabled)
        if self.video_has_loaded and self.logo_enabled and self.logo_pixmap and not self.logo_pixmap.isNull():
            lx = self.logo_x_pct * W
            ly = self.logo_y_pct * H
            lw = self.logo_w_pct * W
            lh = self.logo_h_pct * H
            logo_rect = QRectF(lx, ly, lw, lh)

            painter.drawPixmap(logo_rect.toRect(), self.logo_pixmap)

            painter.setPen(QPen(QColor("#6c5ce7"), 1.5, Qt.DashLine))
            painter.drawRect(logo_rect)

            handle_rect = QRectF(lx + lw - 12, ly + lh - 12, 12, 12)
            painter.fillRect(handle_rect, QColor("#6c5ce7"))

        # 3. Render Draggable Subtitle Text Overlay
        if self.video_has_loaded and self.sub_text:
            painter.setFont(QFont(self.sub_font_family, int(self.sub_font_size * 0.8), QFont.Bold))
            metrics = painter.fontMetrics()
            bounding = metrics.boundingRect(self.sub_text)

            tw = max(120, bounding.width() + 24)
            th = bounding.height() + 12

            sx = self.sub_x_pct * W - (tw / 2.0)
            sy = self.sub_y_pct * H - (th / 2.0)
            sub_rect = QRectF(sx, sy, tw, th)

            painter.setPen(QPen(QColor("#fdcb6e"), 1, Qt.DotLine))
            painter.drawRect(sub_rect)

            painter.setPen(QPen(QColor(self.sub_outline_color), 3))
            painter.drawText(sub_rect, Qt.AlignCenter, self.sub_text)
            painter.setPen(QPen(QColor(self.sub_primary_color)))
            painter.drawText(sub_rect, Qt.AlignCenter, self.sub_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            W = float(self.width())
            H = float(self.height())

            if not self.video_has_loaded:
                self.upload_clicked.emit()
                return

            # Check Blur Handles (Top-Right Close ✖, Bottom-Right Resize ◢, Top-Left 🤚 & Drag Box)
            if self.blur_enabled:
                bx = self.blur_x_pct * W
                by = self.blur_y_pct * H
                bw = self.blur_w_pct * W
                bh = self.blur_h_pct * H

                # 1. Top-Right Close Button ✖
                if QRectF(bx + bw - 15, by - 15, 30, 30).contains(pos):
                    self.set_blur_enabled(False)
                    return
                # 2. Bottom-Right Crop/Resize Handle ◢
                elif QRectF(bx + bw - 15, by + bh - 15, 30, 30).contains(pos):
                    self._dragging_target = "blur_br"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return
                # 3. Top-Left Move Handle 🤚 or inside blur box -> Move box
                elif QRectF(bx - 15, by - 15, 30, 30).contains(pos) or QRectF(bx, by, bw, bh).contains(pos):
                    self._dragging_target = "blur"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return

            # Check Logo Resize handle hit
            if self.logo_enabled:
                lx = self.logo_x_pct * W
                ly = self.logo_y_pct * H
                lw = self.logo_w_pct * W
                lh = self.logo_h_pct * H
                if QRectF(lx + lw - 15, ly + lh - 15, 20, 20).contains(pos):
                    self._dragging_target = "logo_resize"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(lx, ly, lw, lh)
                    return
                elif QRectF(lx, ly, lw, lh).contains(pos):
                    self._dragging_target = "logo"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(lx, ly, lw, lh)
                    return

            # Check Subtitle drag hit
            tw = 200
            th = 40
            sx = self.sub_x_pct * W - (tw / 2.0)
            sy = self.sub_y_pct * H - (th / 2.0)
            sub_rect = QRectF(sx, sy, tw, th)

            if sub_rect.contains(pos) or not (self.logo_enabled or self.blur_enabled):
                self._dragging_target = "sub"
                self._drag_start_pos = pos
                self._element_start_rect = QRectF(sx, sy, tw, th)

    def mouseMoveEvent(self, event):
        if not self._dragging_target or not (event.buttons() & Qt.LeftButton):
            return

        pos = event.position()
        delta_x = pos.x() - self._drag_start_pos.x()
        delta_y = pos.y() - self._drag_start_pos.y()

        W = float(max(1, self.width()))
        H = float(max(1, self.height()))

        if self._dragging_target == "sub":
            new_cx = self._element_start_rect.center().x() + delta_x
            new_cy = self._element_start_rect.center().y() + delta_y
            self.sub_x_pct = max(0.05, min(0.95, new_cx / W))
            self.sub_y_pct = max(0.05, min(0.95, new_cy / H))
            self.subtitle_pos_changed.emit(self.sub_x_pct, self.sub_y_pct)

        elif self._dragging_target == "blur":
            new_x = self._element_start_rect.x() + delta_x
            new_y = self._element_start_rect.y() + delta_y
            self.blur_x_pct = max(0.0, min(0.9, new_x / W))
            self.blur_y_pct = max(0.0, min(0.9, new_y / H))
            self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

        elif self._dragging_target in ("blur_resize", "blur_br"):
            new_w = max(30, self._element_start_rect.width() + delta_x)
            new_h = max(20, self._element_start_rect.height() + delta_y)
            self.blur_w_pct = max(0.03, min(0.95, new_w / W))
            self.blur_h_pct = max(0.03, min(0.95, new_h / H))
            self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

        elif self._dragging_target == "blur_tl":
            new_x = self._element_start_rect.x() + delta_x
            new_y = self._element_start_rect.y() + delta_y
            new_w = max(30, self._element_start_rect.width() - delta_x)
            new_h = max(20, self._element_start_rect.height() - delta_y)
            self.blur_x_pct = max(0.0, min(0.9, new_x / W))
            self.blur_y_pct = max(0.0, min(0.9, new_y / H))
            self.blur_w_pct = max(0.03, min(0.95, new_w / W))
            self.blur_h_pct = max(0.03, min(0.95, new_h / H))
            self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

        elif self._dragging_target == "logo":
            new_x = self._element_start_rect.x() + delta_x
            new_y = self._element_start_rect.y() + delta_y
            self.logo_x_pct = max(0.0, min(0.9, new_x / W))
            self.logo_y_pct = max(0.0, min(0.9, new_y / H))
            self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, self.logo_enabled)

        elif self._dragging_target == "logo_resize":
            new_w = max(30, self._element_start_rect.width() + delta_x)
            new_h = max(30, self._element_start_rect.height() + delta_y)
            self.logo_w_pct = max(0.05, min(0.95, new_w / W))
            self.logo_h_pct = max(0.05, min(0.95, new_h / H))
            self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, self.logo_enabled)

        self.update()

    def mouseReleaseEvent(self, event):
        self._dragging_target = None
