from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QSlider, QFrame
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from ..model.models import SubtitleItem

class TimelineCanvas(QWidget):
    seek_requested = Signal(int)  # ms timestamp

    def __init__(self, parent=None):
        super().__init__(parent)
        self.subtitles: List[SubtitleItem] = []
        self.duration_ms: int = 60000  # Default 60 seconds
        self.current_time_ms: int = 0
        self.zoom_factor: float = 1.0
        self.waveform_data: List[float] = []

        self.setMinimumHeight(150)
        self.setMouseTracking(True)

    def set_subtitles(self, subtitles: List[SubtitleItem]):
        self.subtitles = subtitles
        if subtitles:
            max_end = max(sub.end_ms for sub in subtitles)
            self.duration_ms = max(self.duration_ms, max_end + 5000)
        self.update()

    def set_duration(self, duration_ms: int):
        self.duration_ms = max(1000, duration_ms)
        self.update()

    def set_playhead(self, time_ms: int):
        self.current_time_ms = time_ms
        self.update()

    def set_zoom(self, zoom_val: int):
        self.zoom_factor = zoom_val / 50.0  # Range 0.5x to 4.0x
        self.setMinimumWidth(int(800 * self.zoom_factor))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            x = event.position().x()
            time_ms = self._x_to_ms(x)
            self.seek_requested.emit(time_ms)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            x = event.position().x()
            time_ms = self._x_to_ms(x)
            self.seek_requested.emit(time_ms)

    def _x_to_ms(self, x: float) -> int:
        track_left = 60
        track_width = max(1, self.width() - track_left - 20)
        pct = max(0.0, min(1.0, (x - track_left) / track_width))
        return int(pct * self.duration_ms)

    def _ms_to_x(self, ms: int) -> float:
        track_left = 60
        track_width = max(1, self.width() - track_left - 20)
        pct = max(0.0, min(1.0, ms / max(1, self.duration_ms)))
        return track_left + pct * track_width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        H = self.height()

        # Background track lanes
        painter.fillRect(self.rect(), QColor("#16152b"))

        track_h = 32
        y_text = 40
        y_audio = 80
        y_bgm = 120

        # Draw Lane Labels
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.setPen(QColor("#8ecfae"))
        painter.drawText(10, y_text + 20, "TEXT")
        painter.drawText(10, y_audio + 20, "AUDIO")
        painter.drawText(10, y_bgm + 20, "BGM")

        # Lane dividers
        painter.setPen(QPen(QColor("#242244"), 1))
        painter.drawLine(0, y_text, W, y_text)
        painter.drawLine(0, y_audio, W, y_audio)
        painter.drawLine(0, y_bgm, W, y_bgm)
        painter.drawLine(0, y_bgm + track_h, W, y_bgm + track_h)

        # Draw Time Rulers
        num_ticks = 10
        step_ms = self.duration_ms / num_ticks
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#7b78a8"))

        for i in range(num_ticks + 1):
            ms = int(i * step_ms)
            x = self._ms_to_x(ms)
            sec = int(ms / 1000)
            painter.drawLine(int(x), 20, int(x), 35)
            painter.drawText(int(x) - 15, 18, f"{sec:02d}:0")

        # Draw Subtitle Item Blocks
        for sub in self.subtitles:
            x1 = self._ms_to_x(sub.start_ms)
            x2 = self._ms_to_x(sub.end_ms)
            w = max(4, x2 - x1)

            # Subtitle Text Block
            sub_rect = QRectF(x1, y_text + 3, w, track_h - 6)
            painter.fillRect(sub_rect, QColor(50, 168, 107, 160))
            painter.setPen(QPen(QColor("#8ecfae"), 1))
            painter.drawRoundedRect(sub_rect, 3, 3)

            # Draw label inside block
            text_disp = sub.tgt_text if sub.tgt_text else sub.src_text
            if w > 25:
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Khmer OS Battambang", 8))
                painter.drawText(sub_rect, Qt.AlignCenter, painter.fontMetrics().elidedText(text_disp, Qt.ElideRight, int(w - 6)))

            # Subtitle Audio Block (if generated)
            if sub.audio_path:
                aud_rect = QRectF(x1, y_audio + 3, w, track_h - 6)
                painter.fillRect(aud_rect, QColor(0, 184, 148, 160))
                painter.setPen(QPen(QColor("#55efc4"), 1))
                painter.drawRoundedRect(aud_rect, 3, 3)

        # Draw Red Playhead Line
        px = self._ms_to_x(self.current_time_ms)
        painter.setPen(QPen(QColor("#ff7675"), 2))
        painter.drawLine(int(px), 0, int(px), H)

        # Playhead top handle
        handle_poly = [
            QPointF(px - 6, 0),
            QPointF(px + 6, 0),
            QPointF(px + 6, 8),
            QPointF(px, 14),
            QPointF(px - 6, 8)
        ]
        painter.setBrush(QBrush(QColor("#ff7675")))
        painter.drawPolygon(handle_poly)


class TimelineWidget(QWidget):
    seek_requested = Signal(int)
    generate_transcript_clicked = Signal()  # engine/model now comes from Settings
    translate_clicked = Signal()
    generate_audio_clicked = Signal()
    verify_audio_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Top Control Bar
        tb_layout = QHBoxLayout()

        self.lbl_title = QLabel("Timeline Editor")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #8ecfae;")

        self.lbl_timecode = QLabel("00:00 / 00:00")
        self.lbl_timecode.setStyleSheet("color: #dcdde1; font-family: monospace;")

        # STT engine/model is configured once in Settings > Transcript (STT) — no
        # picker here, just click and go. Button shows a loading state while running.
        self.btn_gen_transcript = QPushButton("🎙️ Generate Transcript")
        self.btn_gen_transcript.setObjectName("ActionBtn")
        self.btn_gen_transcript.setToolTip("Uses the STT engine/model set in Settings > Transcript (STT).")

        # Audio Timing Offset Dropdown
        self.combo_lead_offset = QComboBox()
        self.combo_lead_offset.addItems([
            "0.0s Exact Sync (Default)", "+0.5s Lag", "+1.0s Lag", "+1.5s Lag", "+2.0s Lag",
            "-0.5s Lead", "-1.0s Lead", "-1.5s Lead", "-2.0s Lead"
        ])
        self.combo_lead_offset.setCurrentText("0.0s Exact Sync (Default)")

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Khmer", "English", "Vietnamese", "Thai"])

        self.btn_translate = QPushButton("Translate")
        self.btn_translate.setObjectName("PrimaryBtn")

        self.btn_audio = QPushButton("Generate Audio")

        self.btn_verify_audio = QPushButton("🔍 Verify Voice")
        self.btn_verify_audio.setToolTip(
            "Re-transcribes each generated Khmer clip (sengtha/whisper-base-khmer) and "
            "flags lines where the audio doesn't match the intended text — catches "
            "mispronounced or garbled TTS before export."
        )

        self.lbl_zoom = QLabel("Zoom")
        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(10, 100)
        self.slider_zoom.setValue(50)
        self.slider_zoom.setFixedWidth(80)

        self.btn_fit = QPushButton("Fit")

        tb_layout.addWidget(self.lbl_title)
        tb_layout.addWidget(self.lbl_timecode)
        tb_layout.addSpacing(10)
        tb_layout.addWidget(self.btn_gen_transcript)
        tb_layout.addSpacing(10)
        tb_layout.addWidget(self.combo_lang)
        tb_layout.addWidget(self.btn_translate)
        tb_layout.addWidget(self.combo_lead_offset)
        tb_layout.addWidget(self.btn_audio)
        tb_layout.addWidget(self.btn_verify_audio)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_zoom)
        tb_layout.addWidget(self.slider_zoom)
        tb_layout.addWidget(self.btn_fit)

        layout.addLayout(tb_layout)

        # Canvas Timeline
        self.canvas = TimelineCanvas()
        layout.addWidget(self.canvas)

        # Connect Signals
        self.btn_gen_transcript.clicked.connect(self.generate_transcript_clicked.emit)
        self.btn_translate.clicked.connect(self.translate_clicked)
        self.btn_audio.clicked.connect(self.generate_audio_clicked)
        self.btn_verify_audio.clicked.connect(self.verify_audio_clicked)
        self.slider_zoom.valueChanged.connect(self.canvas.set_zoom)
        self.btn_fit.clicked.connect(lambda: self.slider_zoom.setValue(50))
        self.canvas.seek_requested.connect(self.seek_requested)

    def load_subtitles(self, subtitles: List[SubtitleItem]):
        self.canvas.set_subtitles(subtitles)

    def set_transcribing(self, active: bool, status: str = ""):
        if active:
            self.btn_gen_transcript.setEnabled(False)
            self.btn_gen_transcript.setText(f"⏳ {status or 'Transcribing...'}")
        else:
            self.btn_gen_transcript.setEnabled(True)
            self.btn_gen_transcript.setText("🎙️ Generate Transcript")

    def set_verifying(self, active: bool, status: str = ""):
        if active:
            self.btn_verify_audio.setEnabled(False)
            self.btn_verify_audio.setText(f"⏳ {status or 'Verifying...'}")
        else:
            self.btn_verify_audio.setEnabled(True)
            self.btn_verify_audio.setText("🔍 Verify Voice")

    def update_playhead(self, time_ms: int, duration_ms: int):
        self.canvas.set_duration(duration_ms)
        self.canvas.set_playhead(time_ms)

        curr_sec = SubtitleItem.ms_to_timecode(time_ms)[:8]
        dur_sec = SubtitleItem.ms_to_timecode(duration_ms)[:8]
        self.lbl_timecode.setText(f"{curr_sec} / {dur_sec}")
