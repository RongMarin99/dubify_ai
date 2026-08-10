import os
import re
from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer
from PySide6.QtGui import (
    QPainter, QColor, QPen, QFont, QPixmap, QBrush, QImage,
    QDragEnterEvent, QDropEvent, QFontMetrics, QPainterPath,
    QLinearGradient, QRadialGradient
)

from ..model.models import SubtitleItem


def wrap_text_to_pixel_width(text: str, metrics: QFontMetrics, max_px: float) -> List[str]:
    """Break text into lines cleanly so no line exceeds max_px in font metrics.
    Handles Khmer (non-spaced), Chinese, English, and multilingual text seamlessly."""
    if not text:
        return [""]

    max_px = max(60.0, max_px)
    lines = []

    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        if metrics.horizontalAdvance(raw_line) <= max_px:
            lines.append(raw_line)
            continue

        # Split on space or ZWSP if available
        tokens = re.split(r'(\s+|\u200b)', raw_line)

        # Pre-process tokens: split any single token wider than max_px into sub-tokens
        sub_tokens = []
        for token in tokens:
            if not token:
                continue
            if metrics.horizontalAdvance(token) <= max_px or token.isspace():
                sub_tokens.append(token)
            else:
                char_buf = ""
                for char in token:
                    if metrics.horizontalAdvance(char_buf + char) <= max_px:
                        char_buf += char
                    else:
                        if char_buf:
                            sub_tokens.append(char_buf)
                        char_buf = char
                if char_buf:
                    sub_tokens.append(char_buf)

        # Accumulate sub_tokens into lines <= max_px
        current_line = ""
        for st in sub_tokens:
            if not current_line:
                current_line = st
            elif metrics.horizontalAdvance(current_line + st) <= max_px:
                current_line += st
            else:
                if current_line.strip():
                    lines.append(current_line.strip())
                current_line = st.lstrip()

        if current_line.strip():
            lines.append(current_line.strip())

    return lines or [text]


class VideoOverlayCanvas(QWidget):
    subtitle_pos_changed = Signal(float, float)  # x_pct, y_pct
    subtitle_font_size_changed = Signal(int)     # new sub_font_size after resize drag
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
        self.aspect_ratio_mode: str = "Original (Keep)"

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
        self.blur_color: str = "#141419"        # Default dark frosted glass tint
        self.blur_opacity: float = 0.18          # Default 18% opacity — glass, not a solid box

        # Drama & Hardcoded Subtitle Blur Presets
        self.blur_preset: str = "standard"       # "standard" (22px) or "heavy" (30px)
        self.blur_radius: float = 22.0           # 22px Standard, 30px Heavy
        self.feather_radius: float = 18.0        # 18px Standard, 24px Heavy
        self.corner_radius: float = 8.0          # 8px Corner Radius

        # Blur Effect PNG Image Asset (User provided asset: blur_effect.png)
        self.blur_mask_pixmap: Optional[QPixmap] = None
        asset_path_1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "blur_effect.png"))
        asset_path_2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "blur_mask_template.png"))
        if os.path.exists(asset_path_1):
            self.blur_mask_pixmap = QPixmap(asset_path_1)
        elif os.path.exists(asset_path_2):
            self.blur_mask_pixmap = QPixmap(asset_path_2)

        # Drag Interaction State
        self._dragging_target: Optional[str] = None  # "sub", "sub_resize", "logo", "logo_resize", "blur", "blur_resize"
        self._drag_start_pos: QPointF = QPointF()
        self._element_start_rect: QRectF = QRectF()
        self._element_start_font_size: int = 24

        # Callable(QRectF) -> Optional[QImage]: supplies the live video frame under a
        # rect (in this widget's own coordinates) so the blur box can preview a real blur.
        self._frame_provider = None
        self._blur_preview_cache: Optional[QImage] = None

        # Refreshing the blur preview briefly hides/shows the overlay proxy (see
        # grab_scene_region) — doing that synchronously inside paintEvent() flickered
        # the widget's visibility on every update(), which killed the mouse grab mid-drag.
        # A timer decouples the grab from paint/mouse handling; it skips while dragging.
        self._blur_preview_timer = QTimer(self)
        self._blur_preview_timer.setInterval(200)
        self._blur_preview_timer.timeout.connect(self._refresh_blur_preview)
        self._blur_preview_timer.start()

    def load_blur_image(self, image_path: str):
        """Load a custom blur mask texture image."""
        if os.path.exists(image_path):
            pix = QPixmap(image_path)
            if not pix.isNull():
                self.blur_mask_pixmap = pix
                self.update()

    def set_blur_preset(self, preset_name: str):
        """Toggle between Pure Transparent, Standard Drama (22px), Heavy Chinese (30px), and Dark Banner Mask.

        Drives blur_color/blur_opacity directly — those are the values actually painted
        in the preview AND baked into the exported video, so preset == final result.
        """
        if preset_name == "banner":
            self.blur_preset = "banner"
            self.blur_radius = 25.0
            self.feather_radius = 12.0
            self.corner_radius = 8.0
            self.blur_color = "#0a0a0f"
            self.blur_opacity = 0.94                    # Solid dark mask box (intentionally opaque)
        elif preset_name == "transparent":
            self.blur_preset = "transparent"
            self.blur_radius = 22.0
            self.feather_radius = 18.0
            self.corner_radius = 8.0
            self.blur_color = "#000000"
            self.blur_opacity = 0.0                      # 100% transparent glass blur (0% tint)
        elif preset_name == "heavy":
            self.blur_preset = "heavy"
            self.blur_radius = 30.0
            self.feather_radius = 24.0
            self.corner_radius = 8.0
            self.blur_color = "#0f0f14"
            self.blur_opacity = 0.22
        else:
            self.blur_preset = "standard"
            self.blur_radius = 22.0
            self.feather_radius = 18.0
            self.corner_radius = 8.0
            self.blur_color = "#141419"
            self.blur_opacity = 0.18
        self.update()

    def set_blur_color(self, color_hex: str, opacity: float = 0.85):
        """Update blur mask background color and transparency in real time."""
        self.blur_color = color_hex
        self.blur_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def set_frame_provider(self, fn):
        """Register the callback used to grab a live video frame for the blur preview."""
        self._frame_provider = fn

    def _refresh_blur_preview(self):
        if not self.blur_enabled or self._dragging_target is not None:
            return
        provider = self._frame_provider
        if provider is None:
            return
        W = float(max(1, self.width()))
        H = float(max(1, self.height()))
        
        frame_rect = self.get_inner_video_rect() if self.video_has_loaded else QRectF(0, 0, W, H)
        bx = frame_rect.left() + self.blur_x_pct * frame_rect.width()
        by = frame_rect.top() + self.blur_y_pct * frame_rect.height()
        bw = self.blur_w_pct * frame_rect.width()
        bh = self.blur_h_pct * frame_rect.height()
        blur_rect = QRectF(bx, by, bw, bh)
        
        frame = provider(blur_rect)
        if frame is not None and not frame.isNull():
            self._blur_preview_cache = self._fast_blur_image(frame, self.blur_radius)
            self.update()

    @staticmethod
    def _fast_blur_image(image: QImage, radius: float) -> QImage:
        """Cheap, strong-looking blur: downscale then upscale with smooth interpolation.
        Real per-pixel gaussian would be too slow to run on every repaint during playback;
        this downsample trick is the standard fast approximation and matches what the
        ffmpeg boxblur export produces closely enough for a live preview."""
        w, h = image.width(), image.height()
        if w <= 0 or h <= 0:
            return image
        factor = max(2, int(max(1.0, radius) / 3))
        small_w = max(1, w // factor)
        small_h = max(1, h // factor)
        small = image.scaled(small_w, small_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def set_video_loaded(self, loaded: bool):
        self.video_has_loaded = loaded
        self.update()

    def set_aspect_ratio_mode(self, mode: str):
        """Set active display aspect ratio (e.g. '9:16 (Portrait)', '16:9 (Landscape)', 'Original (Keep)')."""
        self.aspect_ratio_mode = mode
        self.update()

    def set_video_aspect_ratio(self, aspect: float):
        """Set original source video aspect ratio (width / height)."""
        if aspect > 0.1:
            self.video_aspect_ratio = aspect
            self.update()

    def get_active_video_rect(self) -> QRectF:
        """Calculate container aspect frame rectangle inside canvas (W, H)."""
        W = float(max(1, self.width()))
        H = float(max(1, self.height()))
        mode = getattr(self, 'aspect_ratio_mode', 'Original (Keep)')

        target_aspect = None
        if "9:16" in mode:
            target_aspect = 9.0 / 16.0
        elif "16:9" in mode:
            target_aspect = 16.0 / 9.0
        elif "1:1" in mode:
            target_aspect = 1.0 / 1.0
        elif "4:5" in mode:
            target_aspect = 4.0 / 5.0

        if target_aspect is not None:
            if (W / H) > target_aspect:
                fh = H
                fw = H * target_aspect
                fx = (W - fw) / 2.0
                fy = 0.0
            else:
                fw = W
                fh = W / target_aspect
                fx = 0.0
                fy = (H - fh) / 2.0
            return QRectF(fx, fy, fw, fh)

        return QRectF(0, 0, W, H)

    def get_inner_video_rect(self) -> QRectF:
        """Calculate actual inner video image rectangle (accounting for letterboxing/pillarboxing)."""
        active_rect = self.get_active_video_rect()
        fx, fy = active_rect.left(), active_rect.top()
        fw, fh = active_rect.width(), active_rect.height()
        v_aspect = getattr(self, 'video_aspect_ratio', 16.0 / 9.0)

        if (fw / fh) > v_aspect:
            vh = fh
            vw = fh * v_aspect
            vx = fx + (fw - vw) / 2.0
            vy = fy
        else:
            vw = fw
            vh = fw / v_aspect
            vx = fx
            vy = fy + (fh - vh) / 2.0
        return QRectF(vx, vy, vw, vh)

    def get_relative_blur_config(self) -> Dict[str, Any]:
        """Return blur box coordinates (0.0 to 1.0) relative to the active video frame."""
        return {
            "x": max(0.0, min(0.95, float(self.blur_x_pct))),
            "y": max(0.0, min(0.95, float(self.blur_y_pct))),
            "w": max(0.03, min(1.0, float(self.blur_w_pct))),
            "h": max(0.03, min(1.0, float(self.blur_h_pct))),
            "enabled": self.blur_enabled,
            "radius": self.blur_radius,
            "color": self.blur_color,
            "opacity": self.blur_opacity
        }

    def get_relative_logo_config(self) -> Dict[str, Any]:
        """Return logo box coordinates (0.0 to 1.0) relative to the inner video image."""
        return {
            "path": self.logo_path,
            "x": max(0.0, min(0.95, float(self.logo_x_pct))),
            "y": max(0.0, min(0.95, float(self.logo_y_pct))),
            "w": max(0.01, min(1.0, float(self.logo_w_pct))),
            "h": max(0.01, min(1.0, float(self.logo_h_pct))),
            "enabled": self.logo_enabled
        }

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
        """One-click default: a wide band over the bottom safe area, where hardcoded
        source subtitles actually live — so most of the time no drag/resize is needed."""
        self.blur_x_pct = 0.08
        self.blur_y_pct = 0.78
        self.blur_w_pct = 0.84
        self.blur_h_pct = 0.16
        self.set_blur_preset("standard")  # guaranteed-good glass look, not whatever was left over
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

        # 0. Render Aspect Ratio Guide Frame (e.g. 9:16 Portrait boundary outline & letterbox dimming)
        mode = getattr(self, 'aspect_ratio_mode', 'Original (Keep)')
        if mode != "Original (Keep)" and self.video_has_loaded:
            active_rect = self.get_active_video_rect()
            painter.save()
            outer_path = QPainterPath()
            outer_path.addRect(QRectF(0, 0, W, H))
            inner_path = QPainterPath()
            inner_path.addRect(active_rect)
            mask_path = outer_path.subtracted(inner_path)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.drawPath(mask_path)

            painter.setPen(QPen(QColor(59, 130, 246, 200), 1.5, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(active_rect)
            painter.restore()

        # Center Upload Card if no video is loaded
        if not self.video_has_loaded:
            cw, ch = 340, 150
            cx = (W - cw) / 2.0
            cy = (H - ch) / 2.0
            card_rect = QRectF(cx, cy, cw, ch)

            painter.fillRect(card_rect, QColor("#1c1a33"))
            painter.setPen(QPen(QColor("#32a86b"), 2, Qt.DashLine))
            painter.drawRoundedRect(card_rect, 10, 10)

            painter.setFont(QFont("Segoe UI", 28))
            painter.setPen(QColor("#8ecfae"))
            painter.drawText(QRectF(cx, cy + 15, cw, 45), Qt.AlignCenter, "📁")

            painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(cx, cy + 65, cw, 25), Qt.AlignCenter, "Click to Upload Video")

            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor("#8c89b4"))
            painter.drawText(QRectF(cx, cy + 95, cw, 35), Qt.AlignCenter, "or Drag & Drop MP4 / MKV / AVI here")

            # 1. Render Blur Box Mask (if enabled)
        if self.blur_enabled:
            frame_rect = self.get_inner_video_rect() if self.video_has_loaded else QRectF(0, 0, W, H)
            bx = frame_rect.left() + self.blur_x_pct * frame_rect.width()
            by = frame_rect.top() + self.blur_y_pct * frame_rect.height()
            bw = self.blur_w_pct * frame_rect.width()
            bh = self.blur_h_pct * frame_rect.height()
            blur_rect = QRectF(bx, by, bw, bh)

            path = QPainterPath()
            path.addRoundedRect(blur_rect, self.corner_radius, self.corner_radius)

            painter.save()
            painter.setClipPath(path)

            # Live frosted glass — draw the cached blurred frame (refreshed on a timer,
            # not synchronously here — see _refresh_blur_preview for why).
            blurred_frame = self._blur_preview_cache

            if blurred_frame is not None:
                painter.drawImage(blur_rect, blurred_frame)
            else:
                # No live frame yet (video not loaded) — dim placeholder so the box isn't empty
                painter.fillRect(blur_rect, QColor(30, 30, 36, 160))

            # Frosted color tint on top of the real blur (adds the glass color cast)
            glass_col = QColor(self.blur_color)
            glass_col.setAlphaF(self.blur_opacity)
            painter.fillRect(blur_rect, glass_col)

            # Glass shine — soft light gradient across the top half (real "glass panel" look)
            shine = QLinearGradient(blur_rect.topLeft(), QPointF(blur_rect.left(), blur_rect.top() + blur_rect.height() * 0.6))
            shine.setColorAt(0.0, QColor(255, 255, 255, 46))
            shine.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.fillRect(blur_rect, QBrush(shine))

            painter.restore()

            # Thin bright edge highlight along the top (glass rim reflection)
            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
            painter.drawLine(QPointF(blur_rect.left() + self.corner_radius, blur_rect.top() + 1),
                              QPointF(blur_rect.right() - self.corner_radius, blur_rect.top() + 1))

            # Selection border (editing-mode indicator only, not baked into export)
            border_color = QColor("#4bb27d") if getattr(self, '_hover_blur', False) else QColor("#32a86b")
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

            # Move Handle (🤚) Top Center Left (#32a86b)
            mv_rect = QRectF(bx + bw / 2.0 - 24, by - 22, 20, 20)
            painter.fillRect(mv_rect, QColor("#32a86b"))
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(mv_rect, Qt.AlignCenter, "🤚")

            # Color & Transparency Handle (🎨) Top Center Right (#5fbb8c)
            col_rect = QRectF(bx + bw / 2.0 + 2, by - 22, 20, 20)
            painter.fillRect(col_rect, QColor("#5fbb8c"))
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
            frame_rect = self.get_inner_video_rect() if self.video_has_loaded else QRectF(0, 0, W, H)
            lx = frame_rect.left() + self.logo_x_pct * frame_rect.width()
            ly = frame_rect.top() + self.logo_y_pct * frame_rect.height()
            lw = self.logo_w_pct * frame_rect.width()
            lh = self.logo_h_pct * frame_rect.height()
            logo_rect = QRectF(lx, ly, lw, lh)

            painter.drawPixmap(logo_rect.toRect(), self.logo_pixmap)
            painter.setPen(QPen(QColor("#32a86b"), 1.5, Qt.DashLine))
            painter.drawRect(logo_rect)

            handle_rect = QRectF(lx + lw - 12, ly + lh - 12, 12, 12)
            painter.fillRect(handle_rect, QColor("#32a86b"))

        # 3. Render Real-Time Subtitle Overlay Object
        if self.is_sub_visible and self.sub_text:
            self._render_subtitle_overlay(painter, W, H)

    def _measure_subtitle_box(self, W: float, H: float):
        """Compute subtitle box geometry — shared by paint() AND hit-testing so the
        drag/resize handles always line up with what's actually drawn.
        Strictly constrained within active video frame boundaries (e.g. 9:16 vertical frame)."""
        active_rect = self.get_active_video_rect()
        ax, ay = active_rect.left(), active_rect.top()
        aw, ah = active_rect.width(), active_rect.height()

        font_weight = QFont.Bold if self.sub_bold else QFont.Normal
        scale_ratio = ah / 720.0  # Scale font proportionally to container height
        rel_font_size = max(13, int(self.sub_font_size * max(0.6, scale_ratio)))

        font = QFont(self.sub_font_family, rel_font_size, font_weight)
        font.setItalic(self.sub_italic)
        metrics = QFontMetrics(font)

        # Max allowed width inside active video frame (88% of active width)
        max_allowed_width = max(100.0, aw * 0.88)
        lines = wrap_text_to_pixel_width(self.sub_text, metrics, max_allowed_width - 32)

        line_height = metrics.height()
        total_height = line_height * len(lines) + 16
        max_line_w = max([metrics.horizontalAdvance(l) for l in lines] or [120])
        total_width = min(max_allowed_width, max(120.0, max_line_w + 32))

        # Compute position relative to active_rect
        if self.sub_alignment == "Bottom Left":
            sx = ax + (self.sub_x_pct * aw)
        elif self.sub_alignment == "Bottom Right":
            sx = ax + (self.sub_x_pct * aw) - total_width
        else:  # Center
            sx = ax + (self.sub_x_pct * aw) - (total_width / 2.0)

        sy = ay + (self.sub_y_pct * ah) - (total_height / 2.0)

        # Safe area bounds constraint — strictly inside active video frame
        sx = max(ax + 4, min(ax + aw - total_width - 4, sx))
        sy = max(ay + 4, min(ay + ah - total_height - 4, sy))

        return sx, sy, total_width, total_height, lines, line_height, font, metrics

    def _render_subtitle_overlay(self, painter: QPainter, W: float, H: float):
        sx, sy, total_width, total_height, lines, line_height, font, metrics = self._measure_subtitle_box(W, H)
        painter.setFont(font)
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

            # Resize Handle (⤡) Bottom Right — drag to scale subtitle font size
            resize_rect = QRectF(sx + total_width - 12, sy + total_height - 12, 16, 16)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#3b82f6")))
            painter.drawEllipse(resize_rect)
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawLine(resize_rect.center() + QPointF(-4, 4), resize_rect.center() + QPointF(4, -4))

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

            # Subtitle Overlay hit test — checked FIRST: subtitles paint on top of the
            # blur box (paint() renders blur, then logo, then subtitle last), so when
            # the two overlap, the subtitle must win the click, not the blur box under it.
            # Geometry matches _render_subtitle_overlay exactly.
            if self.is_sub_visible and self.sub_text:
                sx, sy, tw, th, _lines, _lh, _font, _metrics = self._measure_subtitle_box(W, H)
                sub_rect = QRectF(sx, sy, tw, th)

                # Check Style, Delete & Resize handles on selection box
                if self.is_sub_selected:
                    if QRectF(sx + tw - 40, sy - 24, 20, 20).contains(pos):
                        self.style_edit_requested.emit()
                        return
                    elif QRectF(sx + tw - 16, sy - 24, 20, 20).contains(pos):
                        self.delete_sub_requested.emit()
                        return
                    elif QRectF(sx + tw - 14, sy + th - 14, 20, 20).contains(pos):
                        self._dragging_target = "sub_resize"
                        self._drag_start_pos = pos
                        self._element_start_rect = QRectF(sx, sy, tw, th)
                        self._element_start_font_size = self.sub_font_size
                        return

                if sub_rect.contains(pos) or not (self.logo_enabled or self.blur_enabled):
                    self.is_sub_selected = True
                    self.subtitle_selected.emit(True)
                    self._dragging_target = "sub"
                    self._drag_start_pos = pos
                    self._element_start_rect = QRectF(sx, sy, tw, th)
                    self.update()
                    return

            # Logo handles hit test
            if self.logo_enabled:
                frame_rect = self.get_inner_video_rect() if self.video_has_loaded else QRectF(0, 0, W, H)
                lx = frame_rect.left() + self.logo_x_pct * frame_rect.width()
                ly = frame_rect.top() + self.logo_y_pct * frame_rect.height()
                lw = self.logo_w_pct * frame_rect.width()
                lh = self.logo_h_pct * frame_rect.height()
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

            # Blur handles hit test
            if self.blur_enabled:
                frame_rect = self.get_inner_video_rect() if self.video_has_loaded else QRectF(0, 0, W, H)
                bx = frame_rect.left() + self.blur_x_pct * frame_rect.width()
                by = frame_rect.top() + self.blur_y_pct * frame_rect.height()
                bw = self.blur_w_pct * frame_rect.width()
                bh = self.blur_h_pct * frame_rect.height()

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
            active_rect = self.get_active_video_rect()
            ax, ay = active_rect.left(), active_rect.top()
            aw, ah = float(max(1, active_rect.width())), float(max(1, active_rect.height()))

            new_cx = self._element_start_rect.center().x() + delta_x
            new_cy = self._element_start_rect.center().y() + delta_y
            self.sub_x_pct = max(0.05, min(0.95, (new_cx - ax) / aw))
            self.sub_y_pct = max(0.05, min(0.95, (new_cy - ay) / ah))
            self.subtitle_pos_changed.emit(self.sub_x_pct, self.sub_y_pct)

        elif self._dragging_target == "sub_resize":
            start_w = max(1.0, self._element_start_rect.width())
            new_w = max(60.0, self._element_start_rect.width() + delta_x)
            scale = new_w / start_w
            new_size = int(max(12, min(96, round(self._element_start_font_size * scale))))
            if new_size != self.sub_font_size:
                self.sub_font_size = new_size

        elif self._dragging_target.startswith("blur") or self._dragging_target.startswith("logo"):
            frame_rect = self.get_inner_video_rect() if self.video_has_loaded else QRectF(0, 0, W, H)
            ax, ay = frame_rect.left(), frame_rect.top()
            aw, ah = float(max(1, frame_rect.width())), float(max(1, frame_rect.height()))

            if self._dragging_target == "blur":
                new_x = self._element_start_rect.x() + delta_x
                new_y = self._element_start_rect.y() + delta_y
                self.blur_x_pct = max(0.0, min(0.95, (new_x - ax) / aw))
                self.blur_y_pct = max(0.0, min(0.95, (new_y - ay) / ah))
                self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

            elif self._dragging_target == "blur_br":
                new_w = max(20.0, self._element_start_rect.width() + delta_x)
                new_h = max(15.0, self._element_start_rect.height() + delta_y)
                self.blur_w_pct = max(0.03, min(1.0, new_w / aw))
                self.blur_h_pct = max(0.03, min(1.0, new_h / ah))
                self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

            elif self._dragging_target == "blur_tl":
                new_x = self._element_start_rect.x() + delta_x
                new_y = self._element_start_rect.y() + delta_y
                new_w = max(20.0, self._element_start_rect.width() - delta_x)
                new_h = max(15.0, self._element_start_rect.height() - delta_y)
                self.blur_x_pct = max(0.0, min(0.95, (new_x - ax) / aw))
                self.blur_y_pct = max(0.0, min(0.95, (new_y - ay) / ah))
                self.blur_w_pct = max(0.03, min(1.0, new_w / aw))
                self.blur_h_pct = max(0.03, min(1.0, new_h / ah))
                self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

            elif self._dragging_target == "blur_tr":
                new_y = self._element_start_rect.y() + delta_y
                new_w = max(20.0, self._element_start_rect.width() + delta_x)
                new_h = max(15.0, self._element_start_rect.height() - delta_y)
                self.blur_y_pct = max(0.0, min(0.95, (new_y - ay) / ah))
                self.blur_w_pct = max(0.03, min(1.0, new_w / aw))
                self.blur_h_pct = max(0.03, min(1.0, new_h / ah))
                self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

            elif self._dragging_target == "blur_bl":
                new_x = self._element_start_rect.x() + delta_x
                new_w = max(20.0, self._element_start_rect.width() - delta_x)
                new_h = max(15.0, self._element_start_rect.height() + delta_y)
                self.blur_x_pct = max(0.0, min(0.95, (new_x - ax) / aw))
                self.blur_w_pct = max(0.03, min(1.0, new_w / aw))
                self.blur_h_pct = max(0.03, min(1.0, new_h / ah))
                self.blur_changed.emit(self.blur_x_pct, self.blur_y_pct, self.blur_w_pct, self.blur_h_pct, self.blur_enabled)

            elif self._dragging_target == "logo":
                new_x = self._element_start_rect.x() + delta_x
                new_y = self._element_start_rect.y() + delta_y
                self.logo_x_pct = max(0.0, min(0.95, (new_x - ax) / aw))
                self.logo_y_pct = max(0.0, min(0.95, (new_y - ay) / ah))
                self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, self.logo_enabled)

            elif self._dragging_target == "logo_resize":
                new_w = max(20.0, self._element_start_rect.width() + delta_x)
                new_h = max(20.0, self._element_start_rect.height() + delta_y)
                self.logo_w_pct = max(0.02, min(0.8, new_w / aw))
                self.logo_h_pct = max(0.02, min(0.8, new_h / ah))
                self.logo_changed.emit(self.logo_path, self.logo_x_pct, self.logo_y_pct, self.logo_w_pct, self.logo_h_pct, self.logo_enabled)

        self.update()
        self.raise_()

    def mouseReleaseEvent(self, event):
        if self._dragging_target == "sub_resize":
            self.subtitle_font_size_changed.emit(self.sub_font_size)
        was_blur_drag = isinstance(self._dragging_target, str) and self._dragging_target.startswith("blur")
        self._dragging_target = None
        if was_blur_drag:
            self._refresh_blur_preview()  # snap preview to the new box immediately
