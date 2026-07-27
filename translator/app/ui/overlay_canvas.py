import os
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QPixmap, QBrush, QImage,
    QDragEnterEvent, QDropEvent, QFontMetrics, QPainterPath,
    QLinearGradient, QRadialGradient
)

from ..model.models import SubtitleItem


class VideoOverlayCanvas(QWidget):
    subtitle_pos_changed = Signal(float, float)  # x_pct, y_pct
    subtitle_selected = Signal(bool)             # is_selected
    style_edit_requested = Signal()
    delete_sub_requested = Signal()
    logo_changed = Signal(str, float, float, float, float, bool)  # path, x, y, w, h, enabled
    blur_changed = Signal(float, float, float, float, bool)       # x, y, w, h, enabled
    blur_color_requested = Signal()
    blur_preset_requested = Signal()
    upload_clicked = Signal()
    video_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self.video_has_loaded: bool = False

        # Active Subtitle Properties
        self.sub_text: str = ""
        self.is_sub_visible: bool = True
        self.is_sub_selected: bool = False
        self.active_sub_id: Optional[int] = None

        # Position (0.0 to 1.0 relative coordinates)
        self.sub_x_pct: float = 0.50   # Center horizontally by default
        self.sub_y_pct: float = 0.85   # Bottom by default

        # Style Configuration
        self.sub_font_family: str = "Khmer OS Battambang"
        self.sub_font_size: int = 24
        self.sub_bold: bool = True
        self.sub_italic: bool = False
        self.sub_primary_color: str = "#FFFFFF"
        self.sub_outline_color: str = "#000000"
        self.sub_outline_width: int = 2
        self.sub_shadow_color: str = "#000000"
        self.sub_shadow_offset: int = 1
        self.sub_bg_color: str = "#0d0d16"
        self.sub_bg_opacity: float = 0.85
        self.sub_use_bg_box: bool = True
        self.sub_alignment: str = "Bottom Center"  # Bottom Center, Bottom Left, Bottom Right, Top Center, Middle

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
        self.blur_x_pct: float = 0.30
        self.blur_y_pct: float = 0.10
        self.blur_w_pct: float = 0.40
        self.blur_h_pct: float = 0.18
        self.blur_color: str = "#0f0f19"        # Default dark frosted blur background
        self.blur_opacity: float = 0.85          # Default 85% opacity (customizable transparent to solid)

        # Drama & Hardcoded Subtitle Blur Presets
        self.blur_preset: str = "standard"       # "standard" (22px) or "heavy" (30px)
        self.blur_radius: float = 22.0           # 22px Standard, 30px Heavy
        self.feather_radius: float = 18.0        # 18px Standard, 24px Heavy
        self.corner_radius: float = 8.0          # 8px Corner Radius
        self.blur_bg_tint: QColor = QColor(20, 20, 25, 46)  # rgba(20, 20, 25, 0.18)

        # Blur Effect PNG Image Asset (User provided asset: blur_effect.png)
        self.blur_mask_pixmap: Optional[QPixmap] = None
        asset_path_1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "blur_effect.png"))
        asset_path_2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "blur_mask_template.png"))
        if os.path.exists(asset_path_1):
            self.blur_mask_pixmap = QPixmap(asset_path_1)
        elif os.path.exists(asset_path_2):
            self.blur_mask_pixmap = QPixmap(asset_path_2)

        # Drag Interaction State
        self._dragging_target: Optional[str] = None  # "sub", "logo", "logo_resize", "blur", "blur_resize"
        self._drag_start_pos: QPointF = QPointF()
        self._element_start_rect: QRectF = QRectF()

    def load_blur_image(self, image_path: str):
        """Load a custom blur mask texture image."""
        if os.path.exists(image_path):
            pix = QPixmap(image_path)
            if not pix.isNull():
                self.blur_mask_pixmap = pix
                self.update()

    def set_blur_preset(self, preset_name: str):
        """Toggle between Pure Transparent, Standard Drama (22px), Heavy Chinese (30px), and Dark Banner Mask."""
        if preset_name == "banner":
            self.blur_preset = "banner"
            self.blur_radius = 25.0
            self.feather_radius = 12.0
            self.corner_radius = 8.0
            self.blur_bg_tint = QColor(10, 10, 15, 240)   # Solid Dark Mask Box (rgba(10, 10, 15, 0.95))
        elif preset_name == "transparent":
            self.blur_preset = "transparent"
            self.blur_radius = 22.0
            self.feather_radius = 18.0
            self.corner_radius = 8.0
            self.blur_bg_tint = QColor(0, 0, 0, 0)       # 100% Transparent Glass Blur (0% Tint)
        elif preset_name == "heavy":
            self.blur_preset = "heavy"
            self.blur_radius = 30.0
            self.feather_radius = 24.0
            self.corner_radius = 8.0
            self.blur_bg_tint = QColor(15, 15, 20, 56)   # rgba(15, 15, 20, 0.22)
        else:
            self.blur_preset = "standard"
            self.blur_radius = 22.0
            self.feather_radius = 18.0
            self.corner_radius = 8.0
            self.blur_bg_tint = QColor(20, 20, 25, 46)   # rgba(20, 20, 25, 0.18)
        self.update()

    def set_blur_color(self, color_hex: str, opacity: float = 0.85):
        """Update blur mask background color and transparency in real time."""
        self.blur_color = color_hex
        self.blur_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def set_video_loaded(self, loaded: bool):
        self.video_has_loaded = loaded
        self.update()

    def update_playback_position(self, current_ms: int, subtitles: List[SubtitleItem]):
        """Real-time synchronization loop: find active subtitle at current_ms and keep Z-index on top."""
        self.raise_()  # Maintain top Z-index layer over QVideoWidget playback stream
        if not subtitles or not self.video_has_loaded:
            if self.is_sub_visible:
                self.is_sub_visible = False
                self.update()
            elif self.blur_enabled:
                self.update()
            return

        active_item = None
        for s in subtitles:
            if s.start_ms <= current_ms < s.end_ms:
                active_item = s
                break

        if active_item:
            # Prioritize Translated Text (tgt_text) over Source Text (src_text)
            text = (active_item.tgt_text.strip() if active_item.tgt_text and active_item.tgt_text.strip() else active_item.src_text or "").strip()
            if text != self.sub_text or not self.is_sub_visible or active_item.id != self.active_sub_id:
                self.sub_text = text
                self.active_sub_id = active_item.id
                self.is_sub_visible = True
                self.update()
        else:
            if self.is_sub_visible:
                self.sub_text = ""
                self.active_sub_id = None
                self.is_sub_visible = False
                self.update()

    def set_subtitle_text(self, text: str):
        if self.sub_text != text:
            self.sub_text = text
            self.is_sub_visible = bool(text.strip())
            self.update()

    def set_subtitle_style_config(self, cfg: Dict[str, Any]):
        """Update subtitle styling properties in real time."""
        self.sub_font_family = cfg.get("font_name", self.sub_font_family)
        self.sub_font_size = int(cfg.get("font_size", self.sub_font_size))
        self.sub_primary_color = cfg.get("primary_color", self.sub_primary_color)
        self.sub_outline_color = cfg.get("outline_color", self.sub_outline_color)
        self.sub_bg_color = cfg.get("bg_color", self.sub_bg_color)
        self.sub_outline_width = int(cfg.get("outline_width", self.sub_outline_width))
        self.sub_shadow_offset = int(cfg.get("shadow_width", self.sub_shadow_offset))
        self.sub_bold = cfg.get("bold", True)
        self.sub_italic = cfg.get("italic", False)
        self.sub_use_bg_box = cfg.get("use_bg_box", True)
        self.sub_alignment = cfg.get("alignment", self.sub_alignment)
        self.update()

    def apply_style_preset(self, preset_name: str):
        """Apply predefined caption style preset."""
        if "White Clean" in preset_name:
            self.sub_primary_color = "#FFFFFF"
            self.sub_outline_color = "#000000"
            self.sub_outline_width = 2
            self.sub_use_bg_box = False
            self.sub_bold = True
        elif "Subtitle Box" in preset_name or "TikTok" in preset_name:
            self.sub_primary_color = "#FDCE2A"
            self.sub_outline_color = "#000000"
            self.sub_outline_width = 0
            self.sub_bg_color = "#1E1E2E"
            self.sub_use_bg_box = True
            self.sub_bold = True
        elif "Movie" in preset_name or "Gold" in preset_name:
            self.sub_primary_color = "#FFD700"
            self.sub_outline_color = "#000000"
            self.sub_outline_width = 3
            self.sub_use_bg_box = False
            self.sub_bold = True
        elif "Neon" in preset_name and "Cyan" in preset_name:
            self.sub_primary_color = "#00FFFF"
            self.sub_outline_color = "#6C5CE7"
            self.sub_outline_width = 4
            self.sub_use_bg_box = False
            self.sub_bold = True
        elif "Pink Neon" in preset_name:
            self.sub_primary_color = "#FF007F"
            self.sub_outline_color = "#000000"
            self.sub_outline_width = 3
            self.sub_use_bg_box = False
            self.sub_bold = True
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
        self.blur_x_pct = 0.30  # Centered directly over video stream
        self.blur_y_pct = 0.10  # Upper part of video stream
        self.blur_w_pct = 0.40  # 40% width centered
        self.blur_h_pct = 0.18
        self.video_has_loaded = True
        self.set_blur_enabled(True)
        self.show()
        self.raise_()
        self.update()

    def add_subtitle_object(self, text: str = ""):
        self.sub_x_pct = 0.50
        self.sub_y_pct = 0.85
        if text:
            self.sub_text = text
        elif not self.sub_text:
            self.sub_text = "សូមស្វាគមន៍មកកាន់ Dubify Studio"
        self.is_sub_visible = True
        self.is_sub_selected = True
        self.raise_()
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                self.video_dropped.emit(path)

    def load_style_from_db(self, db):
        """Initialize canvas subtitle style properties from database settings."""
        self.sub_font_family = db.get_setting("sub_font_name", "Khmer OS Battambang")
        self.sub_font_size = int(db.get_setting("sub_font_size", "24"))
        self.sub_primary_color = db.get_setting("sub_primary_color", "#FFFFFF")
        self.sub_outline_color = db.get_setting("sub_outline_color", "#000000")
        self.sub_bg_color = db.get_setting("sub_bg_color", "#0d0d16")
        self.sub_outline_width = int(db.get_setting("sub_outline_width", "2"))
        self.sub_shadow_offset = int(db.get_setting("sub_shadow_width", "1"))
        self.sub_bold = db.get_setting("sub_bold", "true") == "true"
        self.sub_italic = db.get_setting("sub_italic", "false") == "true"
        self.sub_use_bg_box = db.get_setting("sub_use_bg_box", "true") == "true"
        self.sub_alignment = db.get_setting("sub_alignment", "Bottom Center")
        self.update()

    # ----------------------------------------------------
    # Rendering Pipeline
    # ----------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        W = float(self.width())
        H = float(self.height())

        if W <= 0 or H <= 0:
            return

        # 0. Center Upload Card if no video is loaded
        if not self.video_has_loaded:
            cw, ch = 340, 150
            cx = (W - cw) / 2.0
            cy = (H - ch) / 2.0
            card_rect = QRectF(cx, cy, cw, ch)

            painter.fillRect(card_rect, QColor("#1c1a33"))
            painter.setPen(QPen(QColor("#6c5ce7"), 2, Qt.DashLine))
            painter.drawRoundedRect(card_rect, 10, 10)

            painter.setFont(QFont("Segoe UI", 28))
            painter.setPen(QColor("#a29bfe"))
            painter.drawText(QRectF(cx, cy + 15, cw, 45), Qt.AlignCenter, "📁")

            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(cx, cy + 65, cw, 25), Qt.AlignCenter, "Click to Upload Video")

            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor("#8c89b4"))
            painter.drawText(QRectF(cx, cy + 95, cw, 35), Qt.AlignCenter, "or Drag & Drop MP4 / MKV / AVI here")

            # 1. Render Blur Box Mask (if enabled)
        if self.blur_enabled:
            bx = self.blur_x_pct * W
            by = self.blur_y_pct * H
            bw = self.blur_w_pct * W
            bh = self.blur_h_pct * H
            blur_rect = QRectF(bx, by, bw, bh)

            path = QPainterPath()
            path.addRoundedRect(blur_rect, 8.0, 8.0)

            # Clean Semi-Transparent Identification Overlay (rgba(124, 77, 255, 0.15) / 15% Alpha)
            # Lets users clearly identify the blur area without obscuring the video underneath
            tint_col = QColor(124, 77, 255, 38)  # 15% alpha
            painter.fillPath(path, tint_col)

            # Solid Purple Selection Border (#7C4DFF, Active/Hover #8B5CF6, 8px Rounded Rect)
            border_color = QColor("#8B5CF6") if getattr(self, '_hover_blur', False) else QColor("#7C4DFF")
            painter.setPen(QPen(border_color, 2, Qt.SolidLine))
            painter.drawPath(path)

            # 4 Corner Resize Handles (#4DA3FF - Blue with White Border)
            hs = 12
            hs_half = hs / 2.0
            handle_brush = QBrush(QColor("#4DA3FF"))
            handle_pen = QPen(QColor("#FFFFFF"), 1)

            # TL
            tl_box = QRectF(bx - hs_half, by - hs_half, hs, hs)
            painter.fillRect(tl_box, handle_brush)
            painter.setPen(handle_pen)
            painter.drawRect(tl_box)

            # TR
            tr_box = QRectF(bx + bw - hs_half, by - hs_half, hs, hs)
            painter.fillRect(tr_box, handle_brush)
            painter.setPen(handle_pen)
            painter.drawRect(tr_box)

            # BL
            bl_box = QRectF(bx - hs_half, by + bh - hs_half, hs, hs)
            painter.fillRect(bl_box, handle_brush)
            painter.setPen(handle_pen)
            painter.drawRect(bl_box)

            # BR
            br_box = QRectF(bx + bw - hs_half, by + bh - hs_half, hs, hs)
            painter.fillRect(br_box, handle_brush)
            painter.setPen(handle_pen)
            painter.drawRect(br_box)

            # Move Handle (🤚) Top Center Left (#7C4DFF)
            mv_rect = QRectF(bx + bw / 2.0 - 24, by - 22, 20, 20)
            painter.fillRect(mv_rect, QColor("#7C4DFF"))
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(mv_rect, Qt.AlignCenter, "🤚")

            # Color & Transparency Handle (🎨) Top Center Right (#9C6EFF)
            col_rect = QRectF(bx + bw / 2.0 + 2, by - 22, 20, 20)
            painter.fillRect(col_rect, QColor("#9C6EFF"))
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(col_rect, Qt.AlignCenter, "🎨")

            # Delete Button Background (#E53935) & Icon (#FFFFFF) Top Right
            del_rect = QRectF(bx + bw + 2, by - 22, 20, 20)
            painter.fillRect(del_rect, QColor("#E53935"))
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(del_rect, Qt.AlignCenter, "✖")

        # 2. Render Logo / Watermark Overlay (if enabled)
        if self.logo_enabled and self.logo_pixmap and not self.logo_pixmap.isNull():
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

        # 3. Render Real-Time Subtitle Overlay Object
        if self.is_sub_visible and self.sub_text:
            self._render_subtitle_overlay(painter, W, H)

    def _render_subtitle_overlay(self, painter: QPainter, W: float, H: float):
        # Configure Font
        font_weight = QFont.Bold if self.sub_bold else QFont.Normal
        scale_ratio = H / 720.0  # Scale font proportionally to container height
        rel_font_size = max(14, int(self.sub_font_size * max(0.6, scale_ratio)))
        
        font = QFont(self.sub_font_family, rel_font_size, font_weight)
        font.setItalic(self.sub_italic)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        
        # Automatic Line Wrapping (Max 2 lines)
        lines = self.sub_text.splitlines()
        if len(lines) == 1 and len(self.sub_text) > 42:
            mid = len(self.sub_text) // 2
            space_idx = self.sub_text.find(" ", mid)
            if space_idx != -1:
                lines = [self.sub_text[:space_idx].strip(), self.sub_text[space_idx:].strip()]
            else:
                lines = [self.sub_text]

        line_height = metrics.height()
        total_height = line_height * len(lines) + 16
        max_line_w = max([metrics.horizontalAdvance(l) for l in lines] or [120])
        total_width = max(140, max_line_w + 32)

        # Compute position from relative percentages
        if self.sub_alignment == "Bottom Left":
            sx = self.sub_x_pct * W
        elif self.sub_alignment == "Bottom Right":
            sx = self.sub_x_pct * W - total_width
        else:  # Center
            sx = self.sub_x_pct * W - (total_width / 2.0)

        sy = self.sub_y_pct * H - (total_height / 2.0)

        # Safe area bounds constraint
        sx = max(10, min(W - total_width - 10, sx))
        sy = max(10, min(H - total_height - 10, sy))

        sub_rect = QRectF(sx, sy, total_width, total_height)

        # 3A. Background Box
        if self.sub_use_bg_box:
            bg_col = QColor(self.sub_bg_color)
            bg_col.setAlphaF(self.sub_bg_opacity)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg_col))
            painter.drawRoundedRect(sub_rect, 6, 6)

        # 3B. Selection Border & Action Handles (CapCut / Premiere style)
        if self.is_sub_selected:
            painter.setPen(QPen(QColor("#3b82f6"), 2, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(sub_rect.adjusted(-4, -4, 4, 4), 6, 6)

            # Move Handle / Top Banner
            handle_rect = QRectF(sx - 4, sy - 24, 70, 20)
            painter.fillRect(handle_rect, QColor("#3b82f6"))
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(handle_rect, Qt.AlignCenter, "🤚 Subtitle")

            # Style Edit Button (🎨)
            style_btn_rect = QRectF(sx + total_width - 40, sy - 24, 20, 20)
            painter.fillRect(style_btn_rect, QColor("#8b5cf6"))
            painter.drawText(style_btn_rect, Qt.AlignCenter, "🎨")

            # Delete Button (✖)
            del_btn_rect = QRectF(sx + total_width - 16, sy - 24, 20, 20)
            painter.fillRect(del_btn_rect, QColor("#ef4444"))
            painter.drawText(del_btn_rect, Qt.AlignCenter, "✖")

            painter.setFont(font)  # Restore font

        # 3C. Render Text with Outline & Drop Shadow
        pri_col = QColor(self.sub_primary_color)
        out_col = QColor(self.sub_outline_color)

        for idx, line in enumerate(lines):
            line_rect = QRectF(sx + 16, sy + 8 + (idx * line_height), total_width - 32, line_height)

            # Shadow
            if self.sub_shadow_offset > 0:
                shadow_rect = line_rect.translated(self.sub_shadow_offset, self.sub_shadow_offset)
                painter.setPen(QColor("#000000"))
                painter.drawText(shadow_rect, Qt.AlignCenter, line)

            # Outline path (text stroke)
            if self.sub_outline_width > 0:
                path = QPainterPath()
                # Compute baseline for path text
                baseline_y = line_rect.y() + metrics.ascent()
                text_x = line_rect.x() + (line_rect.width() - metrics.horizontalAdvance(line)) / 2.0
                path.addText(text_x, baseline_y, font, line)

                pen = QPen(out_col, self.sub_outline_width * 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.strokePath(path, pen)
                painter.fillPath(path, QBrush(pri_col))
            else:
                painter.setPen(pri_col)
                painter.drawText(line_rect, Qt.AlignCenter, line)

    # ----------------------------------------------------
    # Mouse Interaction Events
    # ----------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            W = float(self.width())
            H = float(self.height())

            if not self.video_has_loaded:
                self.upload_clicked.emit()
                return

            # Blur handles hit test
            if self.blur_enabled:
                bx = self.blur_x_pct * W
                by = self.blur_y_pct * H
                bw = self.blur_w_pct * W
                bh = self.blur_h_pct * H

                # Delete (✖) Button
                if QRectF(bx + bw + 2, by - 22, 22, 22).contains(pos):
                    self.set_blur_enabled(False)
                    print(f"[DEBUG LOG] Blur object deleted | scene_added=False | visible=False")
                    return

                # Preset Mode (⚡) Button (Transparent Glass <-> Standard Drama <-> Heavy Chinese <-> Dark Banner Mask)
                if QRectF(bx + bw / 2.0 - 12, by - 22, 22, 22).contains(pos):
                    if self.blur_preset == "transparent":
                        new_preset = "standard"
                    elif self.blur_preset == "standard":
                        new_preset = "heavy"
                    elif self.blur_preset == "heavy":
                        new_preset = "banner"
                    else:
                        new_preset = "transparent"
                    self.set_blur_preset(new_preset)
                    self.blur_preset_requested.emit()
                    print(f"[DEBUG LOG] Blur preset toggled | mode={new_preset} | radius={self.blur_radius}px | feather={self.feather_radius}px")
                    return

                # Color & Transparency (🎨) Button
                if QRectF(bx + bw / 2.0 + 12, by - 22, 22, 22).contains(pos):
                    self.blur_color_requested.emit()
                    return

                # Four Corner Handles (TL, TR, BL, BR)
                if QRectF(bx - 12, by - 12, 24, 24).contains(pos):
                    self._dragging_target = "blur_tl"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return
                elif QRectF(bx + bw - 12, by - 12, 24, 24).contains(pos):
                    self._dragging_target = "blur_tr"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return
                elif QRectF(bx - 12, by + bh - 12, 24, 24).contains(pos):
                    self._dragging_target = "blur_bl"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return
                elif QRectF(bx + bw - 12, by + bh - 12, 24, 24).contains(pos):
                    self._dragging_target = "blur_br"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return
                elif QRectF(bx, by, bw, bh).contains(pos) or QRectF(bx + bw / 2.0 - 12, by - 22, 24, 24).contains(pos):
                    self._dragging_target = "blur"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(bx, by, bw, bh)
                    return

            # Logo handles hit test
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

            # Subtitle Overlay hit test
            if self.is_sub_visible and self.sub_text:
                tw = 300
                th = 60
                sx = self.sub_x_pct * W - (tw / 2.0)
                sy = self.sub_y_pct * H - (th / 2.0)
                sub_rect = QRectF(sx, sy, tw, th)

                # Check Style & Delete action buttons on selection box
                if self.is_sub_selected:
                    if QRectF(sx + tw - 40, sy - 24, 20, 20).contains(pos):
                        self.style_edit_requested.emit()
                        return
                    elif QRectF(sx + tw - 16, sy - 24, 20, 20).contains(pos):
                        self.delete_sub_requested.emit()
                        return

                if sub_rect.contains(pos) or not (self.logo_enabled or self.blur_enabled):
                    self.is_sub_selected = True
                    self.subtitle_selected.emit(True)
                    self._dragging_target = "sub"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(sx, sy, tw, th)
                    self.update()
                    return

            # Clicked empty canvas
            if self.is_sub_selected:
                self.is_sub_selected = False
                self.subtitle_selected.emit(False)
                self.update()

    def mouseMoveEvent(self, event):
        target = getattr(self, '_dragging_target', None)
        if not target or not (event.buttons() & Qt.LeftButton):
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
            print(f"[DEBUG LOG] Blur moved | pos=({self.blur_x_pct:.3f},{self.blur_y_pct:.3f}) | size=({self.blur_w_pct:.3f}x{self.blur_h_pct:.3f}) | zValue=9999 | visible=True")

        elif self._dragging_target == "blur_br":
            new_w = max(30, self._element_start_rect.width() + delta_x)
            new_h = max(20, self._element_start_rect.height() + delta_y)
            self.blur_w_pct = max(0.03, min(0.95, new_w / W))
            self.blur_h_pct = max(0.03, min(0.95, new_h / H))
            self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)
            print(f"[DEBUG LOG] Blur resized BR | size=({self.blur_w_pct:.3f}x{self.blur_h_pct:.3f})")

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
            print(f"[DEBUG LOG] Blur resized TL | pos=({self.blur_x_pct:.3f},{self.blur_y_pct:.3f}) size=({self.blur_w_pct:.3f}x{self.blur_h_pct:.3f})")

        elif self._dragging_target == "blur_tr":
            new_y = self._element_start_rect.y() + delta_y
            new_w = max(30, self._element_start_rect.width() + delta_x)
            new_h = max(20, self._element_start_rect.height() - delta_y)
            self.blur_y_pct = max(0.0, min(0.9, new_y / H))
            self.blur_w_pct = max(0.03, min(0.95, new_w / W))
            self.blur_h_pct = max(0.03, min(0.95, new_h / H))
            self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)
            print(f"[DEBUG LOG] Blur resized TR | pos=({self.blur_x_pct:.3f},{self.blur_y_pct:.3f}) size=({self.blur_w_pct:.3f}x{self.blur_h_pct:.3f})")

        elif self._dragging_target == "blur_bl":
            new_x = self._element_start_rect.x() + delta_x
            new_w = max(30, self._element_start_rect.width() - delta_x)
            new_h = max(20, self._element_start_rect.height() + delta_y)
            self.blur_x_pct = max(0.0, min(0.9, new_x / W))
            self.blur_w_pct = max(0.03, min(0.95, new_w / W))
            self.blur_h_pct = max(0.03, min(0.95, new_h / H))
            self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)
            print(f"[DEBUG LOG] Blur resized BL | pos=({self.blur_x_pct:.3f},{self.blur_y_pct:.3f}) size=({self.blur_w_pct:.3f}x{self.blur_h_pct:.3f})")

        elif self._dragging_target == "logo":
            new_x = self._element_start_rect.x() + delta_x
            new_y = self._element_start_rect.y() + delta_y
            self.logo_x_pct = max(0.0, min(0.9, new_x / W))
            self.logo_y_pct = max(0.0, min(0.9, new_y / H))
            self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, self.logo_enabled)

        elif self._dragging_target == "logo_resize":
            new_w = max(20, self._element_start_rect.width() + delta_x)
            new_h = max(20, self._element_start_rect.height() + delta_y)
            self.logo_w_pct = max(0.02, min(0.8, new_w / W))
            self.logo_h_pct = max(0.02, min(0.8, new_h / H))
            self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, self.logo_enabled)

        self.update()
        self.raise_()

    def mouseReleaseEvent(self, event):
        self._dragging_target = None
