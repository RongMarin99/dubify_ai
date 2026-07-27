import os
import time
import subprocess
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QProgressBar, QGroupBox, QFileDialog, QMessageBox,
    QSpinBox, QFormLayout
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont

class ExportWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, export_mgr, kwargs: Dict[str, Any]):
        super().__init__()
        self.export_mgr = export_mgr
        self.kwargs = kwargs

    def run(self):
        try:
            self.progress.emit(15, "Preparing project & audio tracks...")
            time.sleep(0.3)
            self.progress.emit(35, "Mixing BGM & AI Khmer Voice dubbing tracks...")
            time.sleep(0.3)
            self.progress.emit(60, "FFmpeg rendering video & burning subtitles...")

            success = self.export_mgr.export_video(**self.kwargs)
            if success:
                self.progress.emit(100, "Export Completed Successfully!")
                self.finished.emit(self.kwargs["output_video_path"])
            else:
                err_msg = getattr(self.export_mgr.ffmpeg_mgr, "last_error", "") or "FFmpeg failed to render output video."
                self.failed.emit(err_msg)
        except Exception as e:
            self.failed.emit(str(e))


class ExportSettingsDialog(QDialog):
    def __init__(self, default_video_path: str, duration_ms: int = 60000, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Video Settings — Dubify Studio Pro")
        self.setMinimumWidth(540)
        self.default_video_path = default_video_path
        self.duration_ms = duration_ms
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title Label
        lbl_title = QLabel("🎬 Export Video Settings")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #a29bfe;")
        layout.addWidget(lbl_title)

        # File & Location Group
        file_group = QGroupBox("Output Destination")
        file_layout = QFormLayout(file_group)

        default_dir = os.path.dirname(self.default_video_path) if self.default_video_path else os.path.expanduser("~/Videos")
        default_filename = "dubbed_" + (os.path.basename(self.default_video_path) if self.default_video_path else "output.mp4")
        default_save_path = os.path.join(default_dir, default_filename)

        self.txt_output_path = QLineEdit(default_save_path)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_path)

        path_box = QHBoxLayout()
        path_box.addWidget(self.txt_output_path)
        path_box.addWidget(btn_browse)

        file_layout.addRow("Output File:", path_box)
        layout.addWidget(file_group)

        # Video Quality & Resolution Presets
        preset_group = QGroupBox("Video Resolution & Quality Presets")
        preset_layout = QFormLayout(preset_group)

        self.combo_preset = QComboBox()
        self.combo_preset.addItems([
            "High (1080p FHD)",
            "Medium (720p HD)",
            "Low (480p SD)",
            "Ultra (1440p 2K)",
            "Original Resolution (Keep)",
            "Custom"
        ])
        self.combo_preset.setCurrentText("High (1080p FHD)")
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)

        self.combo_codec = QComboBox()
        self.combo_codec.addItems(["H.264 (avc1 - Recommended)", "H.265 (HEVC)", "MPEG-4"])

        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["30 FPS (Standard)", "60 FPS (Smooth)", "24 FPS (Cinematic)"])

        self.spin_width = QSpinBox()
        self.spin_width.setRange(320, 3840)
        self.spin_width.setValue(1080)
        self.spin_height = QSpinBox()
        self.spin_height.setRange(240, 2160)
        self.spin_height.setValue(1920)
        self.spin_width.setEnabled(False)
        self.spin_height.setEnabled(False)

        res_box = QHBoxLayout()
        res_box.addWidget(self.spin_width)
        res_box.addWidget(QLabel("x"))
        res_box.addWidget(self.spin_height)

        preset_layout.addRow("Preset:", self.combo_preset)
        preset_layout.addRow("Custom Resolution:", res_box)
        preset_layout.addRow("Video Codec:", self.combo_codec)
        preset_layout.addRow("Frame Rate:", self.combo_fps)

        layout.addWidget(preset_group)

        # Audio & Subtitle Options
        opt_group = QGroupBox("Audio & Subtitle Tracks")
        opt_layout = QVBoxLayout(opt_group)

        self.chk_burn_subtitles = QCheckBox("🔥 Burn Subtitles into Video (Hardsub)")
        self.chk_burn_subtitles.setChecked(True)

        self.chk_include_bgm = QCheckBox("🔉 Keep Original BGM & Sound Effects (Preserved SFX)")
        self.chk_include_bgm.setChecked(True)

        self.chk_include_khmer_voice = QCheckBox("🎙️ Include AI Generated Khmer Dubbing Voice")
        self.chk_include_khmer_voice.setChecked(True)

        opt_layout.addWidget(self.chk_burn_subtitles)
        opt_layout.addWidget(self.chk_include_bgm)
        opt_layout.addWidget(self.chk_include_khmer_voice)

        layout.addWidget(opt_group)

        # Estimation Summary Card
        est_card = QGroupBox("Estimated Output Summary")
        est_layout = QFormLayout(est_card)

        duration_sec = self.duration_ms / 1000.0
        est_size_mb = max(2.5, round((duration_sec * 12.0) / 8.0, 1))

        self.lbl_est_size = QLabel(f"~{est_size_mb} MB")
        self.lbl_est_size.setStyleSheet("font-weight: bold; color: #55efc4;")
        self.lbl_est_time = QLabel(f"~{int(duration_sec * 0.4)} seconds")

        est_layout.addRow("Estimated File Size:", self.lbl_est_size)
        est_layout.addRow("Estimated Render Time:", self.lbl_est_time)

        layout.addWidget(est_card)

        # Bottom Dialog Buttons
        btn_box = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_render = QPushButton("🎬 Start Render")
        self.btn_render.setObjectName("PrimaryBtn")
        self.btn_render.setStyleSheet("background-color: #6c5ce7; color: white; font-weight: bold; padding: 8px 20px;")
        self.btn_render.clicked.connect(self.accept)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_render)

        layout.addLayout(btn_box)

    def _browse_path(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Output File Destination", self.txt_output_path.text(), "MP4 Video (*.mp4)")
        if path:
            self.txt_output_path.setText(path)

    def _on_preset_changed(self, text: str):
        if "Custom" in text:
            self.spin_width.setEnabled(True)
            self.spin_height.setEnabled(True)
        else:
            self.spin_width.setEnabled(False)
            self.spin_height.setEnabled(False)
            if "1080p" in text:
                self.spin_width.setValue(1080); self.spin_height.setValue(1920)
            elif "720p" in text:
                self.spin_width.setValue(720); self.spin_height.setValue(1280)
            elif "480p" in text:
                self.spin_width.setValue(480); self.spin_height.setValue(854)
            elif "1440p" in text:
                self.spin_width.setValue(1440); self.spin_height.setValue(2560)

    def get_export_config(self) -> Dict[str, Any]:
        return {
            "output_path": self.txt_output_path.text(),
            "preset": self.combo_preset.currentText(),
            "width": self.spin_width.value(),
            "height": self.spin_height.value(),
            "codec": self.combo_codec.currentText(),
            "fps": self.combo_fps.currentText(),
            "burn_subtitles": self.chk_burn_subtitles.isChecked(),
            "include_bgm": self.chk_include_bgm.isChecked(),
            "include_khmer_voice": self.chk_include_khmer_voice.isChecked()
        }


class RenderProgressDialog(QDialog):
    def __init__(self, output_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rendering Video... — Dubify Studio")
        self.setMinimumWidth(500)
        self.output_path = output_path
        self.start_time = time.time()
        self.is_paused = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.lbl_title = QLabel("🎬 Rendering Video...")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #a29bfe;")
        layout.addWidget(self.lbl_title)

        self.lbl_step = QLabel("Preparing project & audio tracks...")
        self.lbl_step.setStyleSheet("color: #dcdde1; font-size: 12px;")
        layout.addWidget(self.lbl_step)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(5)
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #6c5ce7; }")
        layout.addWidget(self.progress_bar)

        # Stats Label
        stats_box = QHBoxLayout()
        self.lbl_elapsed = QLabel("Elapsed: 00:00")
        self.lbl_speed = QLabel("Speed: 2.5x")
        self.lbl_speed.setStyleSheet("color: #00b894; font-weight: bold;")
        stats_box.addWidget(self.lbl_elapsed)
        stats_box.addStretch()
        stats_box.addWidget(self.lbl_speed)
        layout.addLayout(stats_box)

        # Control Buttons
        btn_box = QHBoxLayout()
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.clicked.connect(self._toggle_pause)

        self.btn_cancel = QPushButton("Cancel Render")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_open_folder = QPushButton("📂 Open Output Folder")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self._open_folder)

        self.btn_open_video = QPushButton("▶ Play Video")
        self.btn_open_video.setEnabled(False)
        self.btn_open_video.clicked.connect(self._open_video)

        btn_box.addWidget(self.btn_pause)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addStretch()
        btn_box.addWidget(self.btn_open_folder)
        btn_box.addWidget(self.btn_open_video)

        layout.addLayout(btn_box)

        # Timer for elapsed time
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)
        self.timer.start(1000)

    def update_progress(self, percent: int, step_desc: str):
        self.progress_bar.setValue(percent)
        self.lbl_step.setText(step_desc)

    def _update_timer(self):
        if not self.is_paused:
            elapsed_sec = int(time.time() - self.start_time)
            m, s = divmod(elapsed_sec, 60)
            self.lbl_elapsed.setText(f"Elapsed: {m:02d}:{s:02d}")

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.setText("▶ Resume")
            self.lbl_step.setText("Rendering Paused.")
        else:
            self.btn_pause.setText("⏸ Pause")
            self.lbl_step.setText("Resuming render...")

    def set_completed(self):
        self.timer.stop()
        self.progress_bar.setValue(100)
        self.lbl_title.setText("✅ Export Completed Successfully!")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #55efc4;")
        self.lbl_step.setText(f"Video exported to: {self.output_path}")
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setText("Close")
        self.btn_open_folder.setEnabled(True)
        self.btn_open_video.setEnabled(True)

    def _open_folder(self):
        folder = os.path.dirname(self.output_path)
        if os.path.exists(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _open_video(self):
        if os.path.exists(self.output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))
