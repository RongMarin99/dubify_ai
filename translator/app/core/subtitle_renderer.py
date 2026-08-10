import os
from typing import List, Dict, Any, Tuple
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QFontMetrics, QBrush, QPen, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF
from ..model.models import SubtitleItem
from .subtitle import SubtitleParser

def wrap_text_to_pixel_width(text: str, metrics: QFontMetrics, max_w: float) -> List[str]:
    """Auto-wrap text to multiple lines strictly within pixel width limit."""
    lines = []
    # If the user already pressed Enter, respect hard newlines
    hard_lines = text.split('\n')
    
    for hl in hard_lines:
        words = hl.split(' ')
        current_line = ""
        for word in words:
            if not current_line:
                current_line = word
            else:
                test_line = current_line + " " + word
                if metrics.horizontalAdvance(test_line) <= max_w:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
        if current_line:
            lines.append(current_line)
            
    # Force break extremely long unbreakable words
    final_lines = []
    for line in lines:
        if metrics.horizontalAdvance(line) > max_w:
            curr = ""
            for char in line:
                if metrics.horizontalAdvance(curr + char) <= max_w:
                    curr += char
                else:
                    final_lines.append(curr)
                    curr = char
            if curr:
                final_lines.append(curr)
        else:
            final_lines.append(line)
            
    return final_lines

class SubtitleRenderer:
    """Headless subtitle renderer that uses Qt's QPainter to generate perfectly synchronized
    transparent PNG frames matching the UI preview layout exact rules."""
    
    def __init__(self, style_config: Dict[str, Any], aspect_ratio_mode: str, target_w: int, target_h: int):
        self.style_config = style_config
        self.aspect_ratio_mode = aspect_ratio_mode
        self.W = float(target_w)
        self.H = float(target_h)
        
        # Unpack style config to instance variables (same as overlay_canvas.py)
        self.sub_font_family = style_config.get("font_name", "Khmer OS Battambang")
        self.sub_font_size = int(style_config.get("font_size", 24))
        self.sub_primary_color = style_config.get("primary_color", "#FFFFFF")
        self.sub_outline_color = style_config.get("outline_color", "#000000")
        self.sub_bg_color = style_config.get("bg_color", "#1E1E2E")
        self.sub_outline_width = int(style_config.get("outline_width", 2))
        self.sub_shadow_offset = int(style_config.get("shadow_width", 1))
        self.sub_bold = style_config.get("bold", True)
        self.sub_italic = style_config.get("italic", False)
        self.sub_use_bg_box = style_config.get("use_bg_box", False)
        self.sub_alignment = style_config.get("alignment", "Bottom Center")
        self.sub_x_pct = float(style_config.get("sub_x_pct", 0.50))
        self.sub_y_pct = float(style_config.get("sub_y_pct", 0.85))
        self.sub_bg_opacity = 0.55

    def get_active_video_rect(self) -> QRectF:
        """Calculate container aspect frame rectangle inside canvas (W, H)."""
        W = self.W
        H = self.H
        mode = self.aspect_ratio_mode

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

    def _measure_subtitle_box(self, text: str):
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
        lines = wrap_text_to_pixel_width(text, metrics, max_allowed_width - 32)

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

    def _render_subtitle_overlay(self, painter: QPainter, text: str):
        sx, sy, total_width, total_height, lines, line_height, font, metrics = self._measure_subtitle_box(text)
        painter.setFont(font)
        sub_rect = QRectF(sx, sy, total_width, total_height)

        # Background Box
        if self.sub_use_bg_box:
            bg_col = QColor(self.sub_bg_color)
            bg_col.setAlphaF(self.sub_bg_opacity)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg_col))
            painter.drawRoundedRect(sub_rect, 6, 6)

        # Render Text with Outline & Drop Shadow
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

    def render_to_png(self, text: str, output_path: str):
        img = QImage(int(self.W), int(self.H), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        self._render_subtitle_overlay(painter, text)
        painter.end()
        img.save(output_path)

    def generate_concat_video(self, subtitles: List[SubtitleItem], output_dir: str) -> str:
        """
        Generates a sequence of PNGs and a concat.txt file for FFmpeg image2 demuxer.
        Returns the path to the concat.txt file.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Create a blank frame
        blank_path = os.path.join(output_dir, "blank.png").replace("\\", "/")
        blank_img = QImage(int(self.W), int(self.H), QImage.Format_ARGB32_Premultiplied)
        blank_img.fill(Qt.transparent)
        blank_img.save(blank_path)
        
        concat_path = os.path.join(output_dir, "concat.txt").replace("\\", "/")
        with open(concat_path, "w", encoding="utf-8") as f:
            f.write("ffconcat version 1.0\n")
            
            last_end_ms = 0
            for idx, item in enumerate(subtitles):
                text = (item.tgt_text if item.tgt_text else item.src_text) or ""
                # Clean up Khmer punctuation formatting similar to what we did in ASS export
                text = text.replace("។", "").replace(".", "").strip()
                
                if item.start_ms > last_end_ms:
                    gap_ms = item.start_ms - last_end_ms
                    f.write(f"file 'blank.png'\n")
                    f.write(f"duration {gap_ms / 1000.0:.3f}\n")
                
                png_path = os.path.join(output_dir, f"sub_{idx}.png").replace("\\", "/")
                self.render_to_png(text, png_path)
                
                dur_ms = item.end_ms - item.start_ms
                f.write(f"file 'sub_{idx}.png'\n")
                f.write(f"duration {dur_ms / 1000.0:.3f}\n")
                
                last_end_ms = item.end_ms
                
            # Keep blank at the end to ensure the last subtitle duration is respected properly
            f.write(f"file 'blank.png'\n")
            
        return concat_path
