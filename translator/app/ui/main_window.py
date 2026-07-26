import os
import re
from typing import List, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QFileDialog, QProgressBar, QStatusBar,
    QMessageBox, QSlider, QFrame, QMenu, QMenuBar, QComboBox, QDialog
)
from PySide6.QtCore import Qt, QUrl, QTimer, QSize, Signal
from PySide6.QtGui import QIcon, QFont, QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from .editor import SubtitleEditorWidget
from .timeline import TimelineWidget
from .setting import SettingsDialog
from .style_dialog import SubtitleStyleDialog
from .overlay_canvas import VideoOverlayCanvas
from ..database.sqlite import DatabaseManager
from ..core.cache import CacheManager
from ..core.ffmpeg import FFmpegManager, AudioExtractWorker
from ..core.whisper import WhisperWorker
from ..core.translator import TranslationWorker
from ..core.tts import TTSWorker
from ..core.exporter import ExportManager
from ..model.models import SubtitleItem, ProjectModel

class VideoPlayerWidget(QFrame):
    video_loaded = Signal(str)  # video path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoPreviewPanel")
        self.setAcceptDrops(True)
        self.video_path: str = ""

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header Title & Quick Toolbar (matching user screenshot layout)
        header_bar = QHBoxLayout()
        lbl_header = QLabel("▶ Video Preview")
        lbl_header.setProperty("class", "PanelTitle")

        self.lbl_video_name = QLabel("")
        self.lbl_video_name.setStyleSheet("color: #8c89b4; font-size: 11px;")

        self.btn_change_video = QPushButton("📂 Change Video")
        self.btn_change_video.setObjectName("PrimaryBtn")

        header_bar.addWidget(lbl_header)
        header_bar.addWidget(self.lbl_video_name)
        header_bar.addStretch()
        header_bar.addWidget(self.btn_change_video)

        layout.addLayout(header_bar)

        # Video Container Frame (Stack VideoWidget + OverlayCanvas)
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: #0b0a14; border-radius: 4px;")
        
        container_layout = QVBoxLayout(self.video_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_widget = QVideoWidget(self.video_container)
        container_layout.addWidget(self.video_widget)
        
        self.overlay_canvas = VideoOverlayCanvas(self.video_container)
        self.overlay_canvas.raise_()

        layout.addWidget(self.video_container, stretch=1)

        # Media Player & Audio Output
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        # Media Player & Audio Output for Main Video
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        # Media Player & Audio Output for Generated Khmer TTS Audio Preview
        self.tts_player = QMediaPlayer()
        self.tts_audio_output = QAudioOutput()
        self.tts_player.setAudioOutput(self.tts_audio_output)

        self.subtitles_ref: List[SubtitleItem] = []
        self.active_tts_sub_id: Optional[int] = None

        # Bottom Player Controls Bar
        ctrl_layout = QHBoxLayout()

        self.btn_play = QPushButton("▶ Play")
        self.btn_stop = QPushButton("■ Stop")
        
        self.btn_loop = QPushButton("🔁")
        self.btn_loop.setCheckable(True)
        self.btn_loop.setFixedWidth(32)

        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(80)
        self.slider_vol.setFixedWidth(80)

        self.btn_logo = QPushButton("🖼️ Logo")
        self.btn_add_blur = QPushButton("➕ Add Blur")
        self.btn_add_blur.setObjectName("PrimaryBtn")
        self.btn_add_sub = QPushButton("➕ Add Subtitle")
        self.btn_add_sub.setObjectName("ActionBtn")
        self.btn_duck_bg = QPushButton("🔉 Speech Ducking")
        self.btn_duck_bg.setCheckable(True)
        self.btn_duck_bg.setChecked(True)

        self.combo_ratio = QComboBox()
        self.combo_ratio.addItems([
            "Original (Keep)", "9:16 (Portrait)", "16:9 (Landscape)", "1:1 (Square)", "4:5 (Vertical)"
        ])

        self.combo_orig_vol = QComboBox()
        self.combo_orig_vol.addItems([
            "🔊 Orig Vol: 0%", "🔊 Orig Vol: 10%", "🔊 Orig Vol: 20%", "🔊 Orig Vol: 30%",
            "🔊 Orig Vol: 40%", "🔊 Orig Vol: 50%", "🔊 Orig Vol: 75%", "🔊 Orig Vol: 100%"
        ])
        self.combo_orig_vol.setCurrentText("🔊 Orig Vol: 20%")

        self.lbl_current_time = QLabel("00:00.00")
        self.lbl_duration = QLabel("00:00.00")

        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_loop)
        ctrl_layout.addWidget(self.slider_vol)
        ctrl_layout.addWidget(self.btn_logo)
        ctrl_layout.addWidget(self.btn_add_blur)
        ctrl_layout.addWidget(self.btn_add_sub)
        ctrl_layout.addWidget(self.btn_duck_bg)
        ctrl_layout.addWidget(self.combo_ratio)
        ctrl_layout.addWidget(self.combo_orig_vol)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.lbl_current_time)
        ctrl_layout.addWidget(QLabel("/"))
        ctrl_layout.addWidget(self.lbl_duration)

        layout.addLayout(ctrl_layout)

        # Signals
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_change_video.clicked.connect(self._on_upload_click_from_canvas)
        self.slider_vol.valueChanged.connect(self.set_volume)
        self.btn_logo.clicked.connect(self._on_select_logo)
        self.btn_add_blur.clicked.connect(self._on_add_blur)
        self.btn_add_sub.clicked.connect(self._on_add_subtitle)
        self.overlay_canvas.upload_clicked.connect(self._on_upload_click_from_canvas)
        self.overlay_canvas.video_dropped.connect(self.load_video)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

    def set_subtitles(self, subtitles: List[SubtitleItem]):
        self.subtitles_ref = subtitles

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay_canvas') and hasattr(self, 'video_container'):
            w = max(10, self.video_container.width())
            h = max(10, self.video_container.height())
            self.overlay_canvas.setGeometry(0, 0, w, h)
            self.overlay_canvas.raise_()

    def _on_select_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Logo / Watermark Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if path:
            self.overlay_canvas.load_logo(path)

    def _on_add_blur(self):
        self.overlay_canvas.add_blur_region()
        self.overlay_canvas.raise_()

    def _on_add_subtitle(self):
        active_text = ""
        pos = self.player.position()
        for sub in self.subtitles_ref:
            if sub.start_ms <= pos <= sub.end_ms:
                active_text = sub.tgt_text if sub.tgt_text else sub.src_text
                break
        self.overlay_canvas.add_subtitle_object(active_text)
        self.overlay_canvas.raise_()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                self.load_video(path)

    def _on_upload_click_from_canvas(self):
        parent_mw = self.window()
        last_dir = ""
        if hasattr(parent_mw, 'db'):
            last_dir = parent_mw.db.get_setting("last_video_dir", "")

        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", last_dir, "Video Files (*.mp4 *.mkv *.avi *.mov)"
        )
        if path:
            self.load_video(path)

    def load_video(self, video_path: str):
        if not video_path or not os.path.exists(video_path):
            return
        self.video_path = video_path
        self.lbl_video_name.setText(os.path.basename(video_path))

        parent_mw = self.window()
        if hasattr(parent_mw, 'db'):
            folder_dir = os.path.dirname(video_path)
            parent_mw.db.set_setting("last_video_dir", folder_dir)
            parent_mw.db.set_setting("last_video_path", video_path)

        self.overlay_canvas.set_video_loaded(True)
        self.overlay_canvas.raise_()
        self.overlay_canvas.update()
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.video_loaded.emit(video_path)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.tts_player.pause()
            self.btn_play.setText("▶ Play")
        else:
            self.player.play()
            self.btn_play.setText("⏸ Pause")

    def stop(self):
        self.player.stop()
        self.tts_player.stop()
        self.active_tts_sub_id = None
        self.btn_play.setText("▶ Play")

    def set_volume(self, val: int):
        vol = val / 100.0
        self.audio_output.setVolume(vol)
        self.tts_audio_output.setVolume(vol)

    def seek(self, ms: int):
        self.player.setPosition(ms)
        self.tts_player.stop()
        self.active_tts_sub_id = None

    def _on_position_changed(self, position: int):
        tc = SubtitleItem.ms_to_timecode(position)[:8]
        self.lbl_current_time.setText(tc)

        # Check if position is currently inside a speech dialogue interval
        is_speech_interval = False
        if self.subtitles_ref:
            for sub in self.subtitles_ref:
                if sub.start_ms <= position <= sub.end_ms:
                    is_speech_interval = True
                    break

        # Dynamic Original Audio Volume Control (0% to 100%)
        import re
        vol_match = re.search(r'\d+', self.combo_orig_vol.currentText())
        vol_pct = int(vol_match.group()) if vol_match else 20
        target_vol = (vol_pct / 100.0) if (self.btn_duck_bg.isChecked() and is_speech_interval) else 1.0
        self.audio_output.setVolume(target_vol)

        # Real-time Khmer TTS Voice Sync during video preview
        if self.subtitles_ref and self.player.playbackState() == QMediaPlayer.PlayingState:
            parent_mw = self.window()
            offset_ms = 0
            if hasattr(parent_mw, 'timeline_widget'):
                lead_text = parent_mw.timeline_widget.combo_lead_offset.currentText()
                if "-2.0s" in lead_text: offset_ms = -2000
                elif "-1.5s" in lead_text: offset_ms = -1500
                elif "-1.0s" in lead_text: offset_ms = -1000
                elif "-0.5s" in lead_text: offset_ms = -500
                elif "+0.5s" in lead_text: offset_ms = 500
                elif "+1.0s" in lead_text: offset_ms = 1000
                elif "+1.5s" in lead_text: offset_ms = 1500
                elif "+2.0s" in lead_text: offset_ms = 2000

            target_pos = position - offset_ms
            for sub in self.subtitles_ref:
                if sub.audio_path and os.path.exists(sub.audio_path):
                    if sub.start_ms <= target_pos <= sub.start_ms + 350:
                        if self.active_tts_sub_id != sub.id:
                            self.active_tts_sub_id = sub.id
                            self.tts_player.setSource(QUrl.fromLocalFile(sub.audio_path))
                            self.tts_player.play()
                        break

    def _on_duration_changed(self, duration: int):
        tc = SubtitleItem.ms_to_timecode(duration)[:8]
        self.lbl_duration.setText(tc)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dubify AI PRO - v1.4.28")
        self.resize(1280, 800)

        self.db = DatabaseManager()
        self.cache_mgr = CacheManager(self.db)
        self.ffmpeg_mgr = FFmpegManager(self.db.get_setting("ffmpeg_path", "ffmpeg"))
        self.export_mgr = ExportManager(self.ffmpeg_mgr)

        self.current_project = ProjectModel()
        self.subtitles: List[SubtitleItem] = []

        self._init_ui()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Header Bar
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(header_frame)

        lbl_logo = QLabel("Dubify AI")
        lbl_logo.setObjectName("AppTitle")
        
        lbl_pro = QLabel("PRO")
        lbl_pro.setObjectName("ProBadge")

        lbl_sub = QLabel("AI Video Translation & Dubbing Studio")
        lbl_sub.setStyleSheet("color: #8c89b4; font-size: 11px;")

        self.btn_status_pro = QPushButton("✓ PRO Activated")
        self.btn_status_pro.setObjectName("ProStatusBadge")

        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(self._open_settings)

        header_layout.addWidget(lbl_logo)
        header_layout.addWidget(lbl_pro)
        header_layout.addSpacing(10)
        header_layout.addWidget(lbl_sub)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_status_pro)
        header_layout.addWidget(self.btn_settings)

        main_layout.addWidget(header_frame)

        # Central Splitter Layout
        main_splitter = QSplitter(Qt.Vertical)

        # Top Splitter (Video Player on Left, Subtitle Editor on Right)
        top_splitter = QSplitter(Qt.Horizontal)

        self.video_player = VideoPlayerWidget()
        self.subtitle_editor = SubtitleEditorWidget()

        top_splitter.addWidget(self.video_player)
        top_splitter.addWidget(self.subtitle_editor)
        top_splitter.setStretchFactor(0, 4)
        top_splitter.setStretchFactor(1, 6)

        # Bottom Timeline
        self.timeline_widget = TimelineWidget()

        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.timeline_widget)
        main_splitter.setStretchFactor(0, 7)
        main_splitter.setStretchFactor(1, 3)

        main_layout.addWidget(main_splitter, stretch=1)

        # Bottom Action Bar
        bottom_bar = QFrame()
        bottom_bar.setObjectName("BottomToolbar")
        bottom_layout = QHBoxLayout(bottom_bar)

        self.btn_add_batch = QPushButton("+ Add to Batch")
        self.btn_batch_proc = QPushButton("⚙ Batch Processing")
        self.btn_load_bgm = QPushButton("Load BGM")
        self.btn_isolate_bgm = QPushButton("Isolate BGM")
        self.btn_import_srt = QPushButton("Import SRT")
        self.btn_export_srt = QPushButton("Export SRT")
        self.btn_export_video = QPushButton("Export Video")
        self.btn_export_video.setObjectName("PrimaryBtn")

        bottom_layout.addWidget(self.btn_add_batch)
        bottom_layout.addWidget(self.btn_batch_proc)
        bottom_layout.addSpacing(20)
        bottom_layout.addWidget(self.btn_load_bgm)
        bottom_layout.addWidget(self.btn_isolate_bgm)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_import_srt)
        bottom_layout.addWidget(self.btn_export_srt)
        bottom_layout.addWidget(self.btn_export_video)

        main_layout.addWidget(bottom_bar)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.setStatusBar(self.status_bar)

        # Connect Signals
        self.video_player.video_loaded.connect(self._on_video_loaded)
        self.video_player.player.positionChanged.connect(self._on_player_position_changed)
        self.subtitle_editor.row_selected.connect(self.video_player.seek)
        self.subtitle_editor.subtitle_changed.connect(self._on_subtitles_changed)
        self.subtitle_editor.style_clicked.connect(self._open_style_dialog)
        self.timeline_widget.seek_requested.connect(self.video_player.seek)
        self.timeline_widget.generate_transcript_clicked.connect(self._start_transcription)
        self.timeline_widget.translate_clicked.connect(self._start_translation)
        self.timeline_widget.generate_audio_clicked.connect(self._start_tts)

        self.btn_import_srt.clicked.connect(self._import_srt)
        self.btn_export_srt.clicked.connect(self._export_srt)
        self.btn_export_video.clicked.connect(self._export_video)
        self.btn_load_bgm.clicked.connect(self._load_external_bgm)
        self.btn_isolate_bgm.clicked.connect(self._start_bgm_isolation)
        self.btn_add_batch.clicked.connect(lambda: QMessageBox.information(self, "Batch Queue", "Added project to Batch Queue."))
        self.btn_batch_proc.clicked.connect(lambda: QMessageBox.information(self, "Batch Processing", "Batch Processing Manager ready for multi-episode queue."))

        # Auto-restore last selected video path on app launch
        last_video = self.db.get_setting("last_video_path", "")
        if last_video and os.path.exists(last_video):
            self.video_player.load_video(last_video)

    def _start_bgm_isolation(self):
        if not self.current_project.audio_path or not os.path.exists(self.current_project.audio_path):
            QMessageBox.warning(self, "Warning", "Please load a video first to extract original audio.")
            return

        self.status_bar.showMessage("Running Demucs v4 AI Source Separation & Vocal Removal...")
        self.progress_bar.show()

        self.bgm_sep_worker = AudioSeparationWorker(
            ffmpeg_mgr=self.ffmpeg_mgr,
            audio_path=self.current_project.audio_path
        )
        self.bgm_sep_worker.progress.connect(self._update_progress)
        self.bgm_sep_worker.finished.connect(self._on_bgm_isolated)
        self.bgm_sep_worker.failed.connect(self._on_worker_failed)
        self.bgm_sep_worker.start()

    def _on_bgm_isolated(self, bgm_path: str, dialogue_path: str, sfx_path: str):
        self.current_project.bgm_path = bgm_path
        self.progress_bar.hide()
        self.status_bar.showMessage(f"AI Vocal Removal Complete! Preserved BGM, SFX & Ambient track ({os.path.basename(bgm_path)}).")
        QMessageBox.information(self, "AI Vocal Removal Complete", "Dialogue track muted/removed successfully.\nPreserved original BGM, SFX, ambience, and environmental sounds for dubbing.")

    def _load_external_bgm(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select External BGM / SFX Audio File", "", "Audio Files (*.mp3 *.wav *.aac *.m4a)")
        if path:
            self.current_project.bgm_path = path
            self.status_bar.showMessage(f"Loaded external BGM/SFX audio track: {os.path.basename(path)}")

    def _open_settings(self):
        dlg = SettingsDialog(self.db, self)
        dlg.exec()

    def _open_style_dialog(self):
        dlg = SubtitleStyleDialog(self.db, self)
        dlg.exec()

    def _get_style_config(self) -> dict:
        return {
            "font_name": self.db.get_setting("sub_font_name", "Segoe UI"),
            "font_size": int(self.db.get_setting("sub_font_size", "24")),
            "primary_color": self.db.get_setting("sub_primary_color", "#FFFFFF"),
            "outline_color": self.db.get_setting("sub_outline_color", "#000000"),
            "outline_width": int(self.db.get_setting("sub_outline_width", "2")),
            "bold": self.db.get_setting("sub_bold", "true") == "true",
            "italic": self.db.get_setting("sub_italic", "false") == "true",
            "alignment": self.db.get_setting("sub_alignment", "Bottom Center")
        }

    def _on_video_loaded(self, video_path: str):
        self.current_project.video_path = video_path
        self.video_player.stop()
        self.subtitles = []
        self.subtitle_editor.load_subtitles([])
        self.timeline_widget.load_subtitles([])

        self.status_bar.showMessage(f"Loaded Video: {os.path.basename(video_path)} — Extracting audio in background...")
        self.progress_bar.show()

        # Extract 16kHz WAV audio for STT asynchronously
        temp_wav = os.path.join("temp", "extracted_audio.wav")
        os.makedirs("temp", exist_ok=True)

        self.audio_extract_worker = AudioExtractWorker(
            ffmpeg_mgr=self.ffmpeg_mgr,
            video_path=video_path,
            output_wav_path=temp_wav
        )
        self.audio_extract_worker.progress.connect(self._update_progress)
        self.audio_extract_worker.finished.connect(self._on_audio_extracted)
        self.audio_extract_worker.failed.connect(self._on_worker_failed)
        self.audio_extract_worker.start()

    def _on_audio_extracted(self, temp_wav: str):
        self.current_project.audio_path = temp_wav
        self.progress_bar.hide()
        self.status_bar.showMessage("Video & audio ready. Select STT Model and click '🎙️ Generate Transcript' to scan video speech.")

    def _start_transcription(self, model_name: str):
        if not self.current_project.video_path:
            QMessageBox.warning(self, "Warning", "Please load a video first.")
            return

        wav_path = self.current_project.audio_path or os.path.join("temp", "extracted_audio.wav")
        if not os.path.exists(wav_path):
            QMessageBox.warning(self, "Warning", "Audio is still extracting from video. Please wait a moment.")
            return

        self.progress_bar.show()
        self.status_bar.showMessage(f"Scanning video audio with STT Model [{model_name}]...")
        self.whisper_worker = WhisperWorker(
            audio_path=wav_path,
            model_size=model_name
        )
        self.whisper_worker.progress.connect(self._update_progress)
        self.whisper_worker.finished.connect(self._on_whisper_finished)
        self.whisper_worker.failed.connect(self._on_worker_failed)
        self.whisper_worker.start()

    def _update_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.status_bar.showMessage(msg)

    def _on_whisper_finished(self, subtitles: List[SubtitleItem]):
        self.progress_bar.hide()
        self.status_bar.showMessage("Speech Recognition complete. Auto-detecting VoxcM2 speaker roles...")
        from .editor import auto_detect_speaker_voice
        for sub in subtitles:
            sub.voice = auto_detect_speaker_voice(sub.src_text, sub.tgt_text)
        self.subtitles = subtitles
        self.subtitle_editor.load_subtitles(self.subtitles)
        self.timeline_widget.load_subtitles(self.subtitles)
        self.video_player.set_subtitles(self.subtitles)

    def _on_subtitles_changed(self):
        self.subtitles = self.subtitle_editor.get_subtitles()
        self.timeline_widget.load_subtitles(self.subtitles)
        self.video_player.set_subtitles(self.subtitles)

    def _start_translation(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Warning", "No subtitles loaded to translate.")
            return

        self.progress_bar.show()
        self.trans_worker = TranslationWorker(
            subtitles=self.subtitles,
            engine_name=self.db.get_setting("ai_provider", "Gemini"),
            api_key=self.db.get_setting("gemini_api_key", ""),
            model_name=self.db.get_setting("ai_model", "gemini-2.5-flash"),
            custom_prompt=self.db.get_setting("system_prompt", ""),
            cache_mgr=self.cache_mgr
        )
        self.trans_worker.progress.connect(self._update_progress)
        self.trans_worker.line_translated.connect(self.subtitle_editor.update_single_translation)
        self.trans_worker.finished.connect(self._on_translation_finished)
        self.trans_worker.failed.connect(self._on_worker_failed)
        self.trans_worker.start()

    def _on_translation_finished(self, translated_subs: List[SubtitleItem]):
        self.progress_bar.hide()
        self.status_bar.showMessage("AI Context Translation completed.")
        self.subtitles = translated_subs
        self.subtitle_editor.load_subtitles(self.subtitles)
        self.timeline_widget.load_subtitles(self.subtitles)
        self.video_player.set_subtitles(self.subtitles)

    def _start_tts(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Warning", "No subtitles loaded for TTS.")
            return

        self.progress_bar.show()
        self.tts_worker = TTSWorker(
            subtitles=self.subtitles,
            output_dir="temp",
            engine=self.db.get_setting("tts_engine", "CosyVoice 2 / VoxcM2"),
            cosyvoice_url=self.db.get_setting("cosyvoice_url", "http://localhost:50000/tts")
        )
        self.tts_worker.progress.connect(self._update_progress)
        self.tts_worker.finished.connect(self._on_tts_finished)
        self.tts_worker.failed.connect(self._on_worker_failed)
        self.tts_worker.start()

    def _on_tts_finished(self, updated_subs: List[SubtitleItem]):
        self.progress_bar.hide()
        self.status_bar.showMessage("TTS Dubbing Audio generation completed.")
        self.subtitles = updated_subs
        self.subtitle_editor.load_subtitles(self.subtitles)
        self.timeline_widget.load_subtitles(self.subtitles)
        self.video_player.set_subtitles(self.subtitles)

    def _on_worker_failed(self, err_msg: str):
        self.progress_bar.hide()
        self.status_bar.showMessage(f"Error: {err_msg}")
        QMessageBox.critical(self, "Error", f"Worker failed: {err_msg}")

    def _on_player_position_changed(self, pos: int):
        dur = self.video_player.player.duration()
        self.timeline_widget.update_playhead(pos, dur)

        # Sync active subtitle overlay text on video frame
        active_sub_text = ""
        for sub in self.subtitles:
            if sub.start_ms <= pos <= sub.end_ms:
                active_sub_text = sub.tgt_text if sub.tgt_text else sub.src_text
                break
        
        style_cfg = self._get_style_config()
        self.video_player.overlay_canvas.set_subtitle_style(
            font_family=style_cfg.get("font_name", "Khmer OS Battambang"),
            font_size=style_cfg.get("font_size", 24),
            primary_color=style_cfg.get("primary_color", "#FFFFFF"),
            outline_color=style_cfg.get("outline_color", "#000000")
        )
        self.video_player.overlay_canvas.set_subtitle_text(active_sub_text)

    def _import_srt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import SRT Subtitles", "", "Subtitles (*.srt)")
        if path:
            from ..core.subtitle import SubtitleParser
            self.subtitles = SubtitleParser.parse_srt(path)
            self.subtitle_editor.load_subtitles(self.subtitles)
            self.timeline_widget.load_subtitles(self.subtitles)
            self.status_bar.showMessage(f"Imported {len(self.subtitles)} subtitle lines.")

    def _export_srt(self):
        if not self.subtitles:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export SRT Subtitles", "output_khmer.srt", "Subtitles (*.srt)")
        if path:
            self.export_mgr.export_srt(self.subtitles, path, use_target=True)
            QMessageBox.information(self, "Exported", f"Subtitles exported successfully to {path}")

    def _export_video(self):
        if not self.current_project.video_path or not self.subtitles:
            QMessageBox.warning(self, "Export Video", "Please load a video and prepare subtitles first.")
            return

        from .export_dialog import ExportSettingsDialog, RenderProgressDialog, ExportWorker
        settings_dlg = ExportSettingsDialog(
            default_video_path=self.current_project.video_path,
            duration_ms=self.video_player.player.duration(),
            parent=self
        )
        if settings_dlg.exec() != QDialog.Accepted:
            return

        cfg = settings_dlg.get_export_config()
        save_path = cfg["output_path"]

        self.export_progress_dlg = RenderProgressDialog(save_path, self)
        self.export_progress_dlg.show()

        # Extract Logo and Blur configuration from interactive VideoOverlayCanvas
        canvas = self.video_player.overlay_canvas
        logo_cfg = {
            "path": canvas.logo_path,
            "x": canvas.logo_x_pct,
            "y": canvas.logo_y_pct,
            "w": canvas.logo_w_pct,
            "h": canvas.logo_h_pct,
            "enabled": canvas.logo_enabled
        }
        blur_cfg = {
            "x": canvas.blur_x_pct,
            "y": canvas.blur_y_pct,
            "w": canvas.blur_w_pct,
            "h": canvas.blur_h_pct,
            "enabled": canvas.blur_enabled
        }

        lead_text = self.timeline_widget.combo_lead_offset.currentText()
        offset_ms = 0
        if "-2.0s" in lead_text: offset_ms = -2000
        elif "-1.5s" in lead_text: offset_ms = -1500
        elif "-1.0s" in lead_text: offset_ms = -1000
        elif "-0.5s" in lead_text: offset_ms = -500
        elif "0.0s" in lead_text: offset_ms = 0
        elif "+0.5s" in lead_text: offset_ms = 500
        elif "+1.0s" in lead_text: offset_ms = 1000
        elif "+1.5s" in lead_text: offset_ms = 1500
        elif "+2.0s" in lead_text: offset_ms = 2000

        vol_match = re.search(r'\d+', self.video_player.combo_orig_vol.currentText())
        orig_vol_pct = int(vol_match.group()) if vol_match else 20

        export_args = {
            "video_path": self.current_project.video_path,
            "subtitles": self.subtitles,
            "output_video_path": save_path,
            "style_config": self._get_style_config(),
            "logo_config": logo_cfg,
            "blur_config": blur_cfg,
            "mute_original_audio": self.video_player.btn_duck_bg.isChecked(),
            "audio_offset_ms": offset_ms,
            "aspect_ratio": cfg["preset"],
            "orig_audio_vol_pct": orig_vol_pct
        }

        self.export_render_worker = ExportWorker(self.export_mgr, export_args)
        self.export_render_worker.progress.connect(self.export_progress_dlg.update_progress)
        self.export_render_worker.finished.connect(lambda path: (self.export_progress_dlg.set_completed(), self.status_bar.showMessage(f"Export Completed: {path}")))
        self.export_render_worker.failed.connect(lambda err: (self.export_progress_dlg.reject(), QMessageBox.critical(self, "Export Failed", f"Render failed: {err}")))
        self.export_render_worker.start()

    def closeEvent(self, event):
        for attr in ["whisper_worker", "audio_extract_worker", "translator_worker", "tts_worker"]:
            worker = getattr(self, attr, None)
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(500)
        event.accept()
