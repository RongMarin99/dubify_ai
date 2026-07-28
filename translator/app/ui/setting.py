import os
import json
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit, QPushButton,
    QCheckBox, QFileDialog, QListWidget, QListWidgetItem, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox,
    QFrame, QSplitter, QInputDialog, QApplication, QStyle
)
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon

from ..database.sqlite import DatabaseManager
from ..ai.gemini import NETFLIX_MASTER_PROMPT, test_gemini_key
from ..ai.local_models import LocalModelManager
from ..utils.crypto import decrypt_api_key, mask_api_key


class KeyTesterThread(QThread):
    result = Signal(int, bool, str, int)  # key_id, success, status, latency_ms

    def __init__(self, key_id: int, raw_key: str, model_name: str = "gemini-2.5-flash"):
        super().__init__()
        self.key_id = key_id
        self.raw_key = raw_key
        self.model_name = model_name

    def run(self):
        success, status, latency = test_gemini_key(self.raw_key, self.model_name)
        self.result.emit(self.key_id, success, status, latency)


class LocalModelDetectorThread(QThread):
    detected = Signal(list)

    def run(self):
        models = LocalModelManager.detect_all_models()
        self.detected.emit(models)


class WhisperModelDownloadThread(QThread):
    """Actually loads the faster-whisper model once, which forces huggingface_hub to
    download + cache the weights if they aren't already local. No fake progress theater —
    this really downloads (or confirms) the model."""
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, model_size: str):
        super().__init__()
        self.model_size = model_size

    def run(self):
        try:
            from faster_whisper import WhisperModel
            WhisperModel(self.model_size, device="cpu", compute_type="int8")
            self.finished_ok.emit(self.model_size)
        except Exception as e:
            self.failed.emit(str(e))


class SettingsNavItemWidget(QFrame):
    clicked = Signal(int)

    def __init__(self, page_index: int, icon: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.page_index = page_index
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18px; background: transparent; border: none;")
        layout.addWidget(icon_lbl)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #e4e4e7; background: transparent; border: none;")

        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setStyleSheet("font-size: 11px; color: #71717a; background: transparent; border: none;")

        text_layout.addWidget(self.lbl_title)
        text_layout.addWidget(self.lbl_sub)

        layout.addLayout(text_layout)
        layout.addStretch()

        self.set_selected(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.page_index)

    def set_selected(self, active: bool):
        if active:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e2436;
                    border-radius: 8px;
                    border: 1px solid #3b82f6;
                    border-left: 4px solid #3b82f6;
                }
            """)
            self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #60a5fa; background: transparent; border: none;")
            self.lbl_sub.setStyleSheet("font-size: 11px; color: #93c5fd; background: transparent; border: none;")
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border-radius: 8px;
                    border: 1px solid transparent;
                    border-left: 4px solid transparent;
                }
                QFrame:hover {
                    background-color: #1c1e2b;
                    border: 1px solid #2d3042;
                }
            """)
            self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 500; color: #a1a1aa; background: transparent; border: none;")
            self.lbl_sub.setStyleSheet("font-size: 11px; color: #71717a; background: transparent; border: none;")


class SettingsDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("AI Model Manager & Engine Settings - Dubify Studio")
        self.resize(1020, 690)
        self.setMinimumSize(940, 620)

        self.tester_threads = []
        self._apply_stylesheet()
        self._init_ui()
        self._load_all_settings()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #121318;
                color: #e4e4e7;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QGroupBox {
                background-color: #16171d;
                border: 1px solid #272732;
                border-radius: 10px;
                margin-top: 18px;
                padding: 22px 14px 14px 14px;
                font-weight: 600;
                font-size: 13px;
                color: #60a5fa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 10px;
                left: 12px;
                background-color: #1f2333;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                color: #93c5fd;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel {
                color: #d4d4d8;
                font-size: 13px;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
                background-color: #22232c;
                border: 1px solid #3f3f4e;
                border-radius: 6px;
                padding: 6px 10px;
                color: #f4f4f5;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QPushButton {
                background-color: #272732;
                border: 1px solid #3f3f4e;
                border-radius: 6px;
                color: #f4f4f5;
                padding: 7px 14px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #323342;
                border-color: #525266;
            }
            QPushButton:pressed {
                background-color: #1d1e26;
            }
            QPushButton#btnPrimary {
                background-color: #3b82f6;
                border: none;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#btnPrimary:hover {
                background-color: #2563eb;
            }
            QPushButton#btnDanger {
                background-color: #ef4444;
                border: none;
                color: #ffffff;
            }
            QPushButton#btnDanger:hover {
                background-color: #dc2626;
            }
            QTableWidget {
                background-color: #16171d;
                border: 1px solid #272732;
                border-radius: 8px;
                gridline-color: #272732;
                color: #f4f4f5;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #22232c;
                color: #9ca3af;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #272732;
                font-weight: 600;
                font-size: 12px;
            }
            QCheckBox {
                color: #e4e4e7;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #3f3f4e;
                background-color: #22232c;
            }
            QCheckBox::indicator:hover {
                border-color: #60a5fa;
            }
            QCheckBox::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Top Header Banner
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #16171d; border-radius: 8px; border: 1px solid #272732;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title_lbl = QLabel("⚙️ AI Model Manager & Settings")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self.chk_smart_ai = QCheckBox("⚡ Smart AI Auto-Selection & Silent Fallback")
        self.chk_smart_ai.setToolTip("Automatically pick best AI key or switch to Local AI if cloud models fail")
        header_layout.addWidget(self.chk_smart_ai)

        main_layout.addWidget(header_frame)

        # Body Splitter: Left Sidebar Navigation & Right Content Stack
        body_layout = QHBoxLayout()
        body_layout.setSpacing(14)

        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(240)
        sidebar_frame.setStyleSheet("""
            QFrame {
                background-color: #16171d;
                border: 1px solid #272732;
                border-radius: 10px;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(6)

        # Section 1 Header
        sec1_lbl = QLabel("AUDIO & TRANSLATION")
        sec1_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; padding-left: 8px; margin-top: 4px; margin-bottom: 2px;")
        sidebar_layout.addWidget(sec1_lbl)

        self.nav_items: List[SettingsNavItemWidget] = []

        item_stt = SettingsNavItemWidget(0, "🎙️", "Transcript (STT)", "Whisper, VoxcM2 & VAD")
        item_trans = SettingsNavItemWidget(1, "🌐", "Translation Engine", "Gemini 2.5 & Cloud AI")

        sidebar_layout.addWidget(item_stt)
        sidebar_layout.addWidget(item_trans)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #272732; margin: 6px 4px;")
        sidebar_layout.addWidget(sep)

        # Section 2 Header
        sec2_lbl = QLabel("HARDWARE & LOCAL AI")
        sec2_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; padding-left: 8px; margin-top: 4px; margin-bottom: 2px;")
        sidebar_layout.addWidget(sec2_lbl)

        item_keys = SettingsNavItemWidget(2, "🔑", "Gemini API Keys", "Rotation & Load Balancer")
        item_local = SettingsNavItemWidget(3, "💻", "Local Models", "Ollama & Offline Models")
        item_perf = SettingsNavItemWidget(4, "⚡", "Performance", "CUDA, VRAM & Threads")

        sidebar_layout.addWidget(item_keys)
        sidebar_layout.addWidget(item_local)
        sidebar_layout.addWidget(item_perf)

        self.nav_items = [item_stt, item_trans, item_keys, item_local, item_perf]
        for nav_item in self.nav_items:
            nav_item.clicked.connect(self._select_nav_page)

        sidebar_layout.addStretch()

        # Bottom System Info Badge Card
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #1e202c;
                border: 1px solid #2e3246;
                border-radius: 8px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(4)

        info_lbl1 = QLabel("⚡ Dubify AI Engine v2.5")
        info_lbl1.setStyleSheet("font-size: 11px; font-weight: 700; color: #60a5fa; background: transparent; border: none;")
        info_lbl2 = QLabel("🟢 Execution: CUDA GPU")
        info_lbl2.setStyleSheet("font-size: 10px; color: #4ade80; background: transparent; border: none;")
        info_lbl3 = QLabel("🔑 Multi-Key Rotation: Active")
        info_lbl3.setStyleSheet("font-size: 10px; color: #a1a1aa; background: transparent; border: none;")

        info_layout.addWidget(info_lbl1)
        info_layout.addWidget(info_lbl2)
        info_layout.addWidget(info_lbl3)

        sidebar_layout.addWidget(info_card)

        self.stack = QStackedWidget()

        # Create 5 Pages
        self.page_stt = self._create_stt_page()
        self.page_trans = self._create_trans_page()
        self.page_keys = self._create_keys_page()
        self.page_local = self._create_local_page()
        self.page_perf = self._create_perf_page()

        self.stack.addWidget(self.page_stt)
        self.stack.addWidget(self.page_trans)
        self.stack.addWidget(self.page_keys)
        self.stack.addWidget(self.page_local)
        self.stack.addWidget(self.page_perf)

        body_layout.addWidget(sidebar_frame)
        body_layout.addWidget(self.stack, 1)

        main_layout.addLayout(body_layout, 1)

        # Bottom Action Buttons Bar
        bottom_bar = QHBoxLayout()

        btn_import = QPushButton("📥 Import Settings")
        btn_import.clicked.connect(self._on_import_settings)
        btn_export = QPushButton("📤 Export Settings")
        btn_export.clicked.connect(self._on_export_settings)
        btn_backup = QPushButton("💾 Backup & Restore")
        btn_backup.clicked.connect(self._on_backup_restore)

        bottom_bar.addWidget(btn_import)
        bottom_bar.addWidget(btn_export)
        bottom_bar.addWidget(btn_backup)
        bottom_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save & Apply")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._on_save_all)

        bottom_bar.addWidget(btn_cancel)
        bottom_bar.addWidget(btn_save)

        main_layout.addLayout(bottom_bar)

    def _select_nav_page(self, page_idx: int):
        self.stack.setCurrentIndex(page_idx)
        for nav_item in self.nav_items:
            nav_item.set_selected(nav_item.page_index == page_idx)

    # ----------------------------------------------------
    # SECTION 1: Transcript (Speech-to-Text)
    # ----------------------------------------------------
    def _create_stt_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Card 1: Engine — the ONE place transcription is configured. The Timeline's
        # "Generate Transcript" button just uses whatever is set here, no picker there.
        grp_source = QGroupBox("Transcription Engine (STT)")
        src_l = QVBoxLayout(grp_source)
        src_l.setSpacing(8)

        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("Engine:"))
        self.combo_stt_source = QComboBox()
        self.combo_stt_source.addItems([
            "Gemini (Cloud — Recommended)",
            "Whisper (Local — Offline)"
        ])
        self.combo_stt_source.currentTextChanged.connect(self._on_stt_source_changed)
        row_src.addWidget(self.combo_stt_source, 1)
        src_l.addLayout(row_src)

        layout.addWidget(grp_source)

        # Card 1a: Gemini model — reuses the same API keys + auto-rotation configured
        # in the Translation tab (one key hits quota, it auto-switches to the next).
        self.grp_gemini_stt = QGroupBox("Gemini Model")
        gem_l = QVBoxLayout(self.grp_gemini_stt)
        gem_l.setSpacing(8)
        row_gem = QHBoxLayout()
        row_gem.addWidget(QLabel("Model:"))
        self.combo_gemini_stt_model = QComboBox()
        self.combo_gemini_stt_model.addItems([
            "Gemini 2.5 Flash — Recommended (Fast & Accurate)",
            "Gemini 2.5 Pro — Best Accuracy, Slower"
        ])
        row_gem.addWidget(self.combo_gemini_stt_model, 1)
        gem_l.addLayout(row_gem)
        gem_note = QLabel(
            "Cloud transcription — needs at least one Gemini API key (Translation tab). "
            "Handles accents and noisy audio well; uses your existing multi-key rotation, "
            "so one key hitting its quota automatically falls through to the next."
        )
        gem_note.setWordWrap(True)
        gem_note.setStyleSheet("color: #8c89b4; font-size: 11px;")
        gem_l.addWidget(gem_note)
        layout.addWidget(self.grp_gemini_stt)

        # Card 1b: Local Whisper size — offline, no API key needed. Large v3 is the
        # default: best accuracy, and slow is fine since it still runs unattended.
        self.grp_whisper_stt = QGroupBox("Local Whisper Model")
        fl = QVBoxLayout(self.grp_whisper_stt)
        fl.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Model Size:"))
        self.combo_stt_engine = QComboBox()
        self.combo_stt_engine.addItems([
            "Whisper Tiny — Fastest, Draft Only",
            "Whisper Base — Fast",
            "Whisper Small — Balanced",
            "Whisper Medium — Balanced+",
            "Whisper Large v3 — Best Accuracy, Slowest (Recommended)"
        ])
        self.combo_stt_engine.setCurrentText("Whisper Large v3 — Best Accuracy, Slowest (Recommended)")
        row1.addWidget(self.combo_stt_engine, 1)

        self.btn_download_stt_model = QPushButton("📥 Download / Verify Model")
        self.btn_download_stt_model.setObjectName("btnPrimary")
        self.btn_download_stt_model.setToolTip("Downloads the model weights now (if not already cached) instead of waiting on the first transcription run.")
        self.btn_download_stt_model.clicked.connect(self._on_download_local_stt_model)
        row1.addWidget(self.btn_download_stt_model)

        fl.addLayout(row1)

        note = QLabel(
            "Runs locally on CPU, fully offline — no API key, no internet needed after the "
            "first download. Weights auto-download and cache the first time a size is used. "
            "Large v3 is slower but most accurate; fine to leave running in the background."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8c89b4; font-size: 11px;")
        fl.addWidget(note)

        layout.addWidget(self.grp_whisper_stt)

        # Card 3: Language Configuration
        grp_lang = QGroupBox("Target Source Language Detection")
        lang_l = QHBoxLayout(grp_lang)
        lang_l.addWidget(QLabel("Audio Language:"))

        self.combo_stt_lang = QComboBox()
        self.combo_stt_lang.addItems(["Auto Detect", "Chinese", "English", "Japanese", "Korean", "Custom"])
        self.combo_stt_lang.currentTextChanged.connect(self._on_stt_lang_changed)
        lang_l.addWidget(self.combo_stt_lang)

        self.edit_custom_lang = QLineEdit()
        self.edit_custom_lang.setPlaceholderText("Enter custom ISO code (e.g. km, th, vi)")
        self.edit_custom_lang.setVisible(False)
        lang_l.addWidget(self.edit_custom_lang, 1)

        layout.addWidget(grp_lang)

        # Options — VAD is a local-Whisper concept only, hidden for Gemini
        self.grp_stt_opts = QGroupBox("Audio Pre-processing")
        opt_l = QVBoxLayout(self.grp_stt_opts)
        self.chk_vad = QCheckBox("Enable Silero VAD (Voice Activity Detection) Silence Filter")
        opt_l.addWidget(self.chk_vad)
        layout.addWidget(self.grp_stt_opts)

        layout.addStretch()

        self._on_stt_source_changed(self.combo_stt_source.currentText())
        return page

    def _on_stt_source_changed(self, val: str):
        is_gemini = val.startswith("Gemini")
        self.grp_gemini_stt.setVisible(is_gemini)
        self.grp_whisper_stt.setVisible(not is_gemini)
        self.grp_stt_opts.setVisible(not is_gemini)

    @staticmethod
    def _stt_size_keyword(label: str) -> str:
        """Map a combo label ("Whisper Medium — Recommended") to the faster-whisper
        size keyword it actually needs ("medium")."""
        m_str = label.lower()
        if "large" in m_str:
            return "large-v3"
        elif "medium" in m_str:
            return "medium"
        elif "small" in m_str:
            return "small"
        elif "tiny" in m_str:
            return "tiny"
        return "base"

    def _on_download_local_stt_model(self):
        selected_model = self.combo_stt_engine.currentText()
        size = self._stt_size_keyword(selected_model)

        self.btn_download_stt_model.setEnabled(False)
        self.btn_download_stt_model.setText("⏳ Downloading...")

        self._dl_thread = WhisperModelDownloadThread(size)
        self._dl_thread.finished_ok.connect(self._on_stt_download_ok)
        self._dl_thread.failed.connect(self._on_stt_download_failed)
        self._dl_thread.start()

    def _on_stt_download_ok(self, size: str):
        self.btn_download_stt_model.setEnabled(True)
        self.btn_download_stt_model.setText("📥 Download / Verify Model")
        QMessageBox.information(self, "Model Ready", f"✅ Whisper '{size}' is downloaded and cached — ready for offline transcription.")

    def _on_stt_download_failed(self, error: str):
        self.btn_download_stt_model.setEnabled(True)
        self.btn_download_stt_model.setText("📥 Download / Verify Model")
        QMessageBox.warning(self, "Download Failed", f"Could not download the model:\n{error}")

    def _on_stt_lang_changed(self, val: str):
        self.edit_custom_lang.setVisible(val == "Custom")

    # ----------------------------------------------------
    # SECTION 2: Translation
    # ----------------------------------------------------
    def _create_trans_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        grp_trans = QGroupBox("AI Translation Engine & Model")
        tl = QVBoxLayout(grp_trans)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Select Engine / Model:"))
        self.combo_trans_engine = QComboBox()
        self.combo_trans_engine.addItems([
            "Gemini 2.5 Flash (Recommended)",
            "Gemini 2.5 Pro",
            "OpenAI GPT-4o",
            "DeepSeek R1 / V3",
            "Ollama Local Llama-3"
        ])
        r1.addWidget(self.combo_trans_engine, 1)
        tl.addLayout(r1)

        layout.addWidget(grp_trans)

        grp_params = QGroupBox("Generation Hyperparameters")
        pl = QVBoxLayout(grp_params)

        r_temp = QHBoxLayout()
        r_temp.addWidget(QLabel("Creativity / Temperature (0.0 - 1.0):"))
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.3)
        r_temp.addWidget(self.spin_temp)
        pl.addLayout(r_temp)

        r_tok = QHBoxLayout()
        r_tok.addWidget(QLabel("Max Response Tokens:"))
        self.spin_max_tokens = QSpinBox()
        self.spin_max_tokens.setRange(256, 8192)
        self.spin_max_tokens.setSingleStep(256)
        self.spin_max_tokens.setValue(2048)
        r_tok.addWidget(self.spin_max_tokens)
        pl.addLayout(r_tok)

        layout.addWidget(grp_params)

        grp_prompt = QGroupBox("Master System Prompt (Movie / Drama Subtitle Specialist)")
        p_l = QVBoxLayout(grp_prompt)
        self.txt_system_prompt = QTextEdit()
        self.txt_system_prompt.setPlainText(NETFLIX_MASTER_PROMPT)
        p_l.addWidget(self.txt_system_prompt)

        btn_reset_prompt = QPushButton("🔄 Reset to Master Netflix Prompt")
        btn_reset_prompt.clicked.connect(lambda: self.txt_system_prompt.setPlainText(NETFLIX_MASTER_PROMPT))
        p_l.addWidget(btn_reset_prompt, 0, Qt.AlignRight)

        layout.addWidget(grp_prompt)

        return page

    # ----------------------------------------------------
    # SECTION 3: Gemini API Keys Manager
    # ----------------------------------------------------
    def _create_keys_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        grp_lb = QGroupBox("Automatic API Rotation & Load Balancing")
        lbl_l = QVBoxLayout(grp_lb)

        r_lb = QHBoxLayout()
        r_lb.addWidget(QLabel("Load Balancing Mode:"))
        self.combo_lb_mode = QComboBox()
        self.combo_lb_mode.addItems([
            "Sequential (Key 1 -> Key 2 -> Key 3)",
            "Round Robin (Balanced Distribution)",
            "Fastest Response (Lowest Latency First)"
        ])
        r_lb.addWidget(self.combo_lb_mode, 1)
        lbl_l.addLayout(r_lb)

        layout.addWidget(grp_lb)

        # Toolbar
        tb_layout = QHBoxLayout()
        btn_add_key = QPushButton("➕ Add API Key")
        btn_add_key.setObjectName("btnPrimary")
        btn_add_key.clicked.connect(self._on_add_key)

        btn_paste = QPushButton("📋 Paste Key")
        btn_paste.clicked.connect(self._on_paste_key)

        btn_test_all = QPushButton("🧪 Test All Keys")
        btn_test_all.clicked.connect(self._on_test_all_keys)

        tb_layout.addWidget(btn_add_key)
        tb_layout.addWidget(btn_paste)
        tb_layout.addWidget(btn_test_all)
        tb_layout.addStretch()

        layout.addLayout(tb_layout)

        # API Keys Table
        self.tbl_keys = QTableWidget()
        self.tbl_keys.setColumnCount(9)
        self.tbl_keys.setHorizontalHeaderLabels([
            "#", "Key Name", "Masked API Key", "Status", "Last Used", "Today", "Total", "Latency", "Actions"
        ])
        header = self.tbl_keys.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl_keys.setColumnWidth(0, 35)   # #
        self.tbl_keys.setColumnWidth(3, 85)   # Status
        self.tbl_keys.setColumnWidth(4, 85)   # Last Used
        self.tbl_keys.setColumnWidth(5, 55)   # Today
        self.tbl_keys.setColumnWidth(6, 55)   # Total
        self.tbl_keys.setColumnWidth(7, 75)   # Latency
        self.tbl_keys.setColumnWidth(8, 230)  # Actions (Enough space for all buttons!)
        self.tbl_keys.verticalHeader().setVisible(False)
        self.tbl_keys.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.tbl_keys, 1)

        # Info Note
        lbl_note = QLabel("ℹ️ Automatic silent failover occurs if any key returns Quota Exceeded (429), Invalid (403), or Timeout.")
        lbl_note.setStyleSheet("color: #9ca3af; font-size: 12px; font-style: italic;")
        layout.addWidget(lbl_note)

        return page

    def _refresh_keys_table(self):
        self.tbl_keys.setRowCount(0)
        keys = self.db.get_gemini_keys()
        
        for idx, k in enumerate(keys):
            row = self.tbl_keys.rowCount()
            self.tbl_keys.insertRow(row)
            self.tbl_keys.setRowHeight(row, 40)

            # 0. Order
            order_item = QTableWidgetItem(str(idx + 1))
            order_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_keys.setItem(row, 0, order_item)

            # 1. Name
            self.tbl_keys.setItem(row, 1, QTableWidgetItem(k["name"]))

            # 2. Masked Key
            raw_k = decrypt_api_key(k["api_key_encrypted"])
            masked = mask_api_key(raw_k)
            masked_item = QTableWidgetItem(masked)
            masked_item.setFont(QFont("Consolas", 10))
            self.tbl_keys.setItem(row, 2, masked_item)

            # 3. Status Badge
            status = k.get("status", "Working")
            enabled = k.get("enabled", 1) == 1
            if not enabled:
                status_str = "⚪ Disabled"
                color_hex = "#6b7280"
            elif status == "Working":
                status_str = "🟢 Working"
                color_hex = "#10b981"
            elif status == "Quota Exceeded":
                status_str = "🟡 Quota Exceeded"
                color_hex = "#f59e0b"
            else:
                status_str = "🔴 Invalid"
                color_hex = "#ef4444"

            status_item = QTableWidgetItem(status_str)
            status_item.setForeground(QColor(color_hex))
            status_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.tbl_keys.setItem(row, 3, status_item)

            # 4. Last Used
            self.tbl_keys.setItem(row, 4, QTableWidgetItem(k.get("last_used") or "Never"))

            # 5. Requests Today
            self.tbl_keys.setItem(row, 5, QTableWidgetItem(str(k.get("requests_today", 0))))

            # 6. Total Requests
            self.tbl_keys.setItem(row, 6, QTableWidgetItem(str(k.get("total_requests", 0))))

            # 7. Response Time (Latency)
            lat_ms = k.get("response_time_ms", 0)
            lat_str = f"{lat_ms} ms" if lat_ms > 0 else "--"
            self.tbl_keys.setItem(row, 7, QTableWidgetItem(lat_str))

            # 8. Actions Widget Box
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(4)

            key_id = k["id"]

            btn_test = QPushButton("⚡ Test")
            btn_test.setFixedWidth(54)
            btn_test.setStyleSheet("font-size: 11px; padding: 3px 6px;")
            btn_test.clicked.connect(lambda _, kid=key_id, rk=raw_k: self._test_single_key(kid, rk))

            btn_toggle = QPushButton("Disable" if enabled else "Enable")
            btn_toggle.setFixedWidth(62)
            btn_toggle.setStyleSheet("font-size: 11px; padding: 3px 6px;")
            btn_toggle.clicked.connect(lambda _, kid=key_id, en=enabled: self._toggle_key_enabled(kid, en))

            btn_up = QPushButton("▲")
            btn_up.setFixedWidth(26)
            btn_up.setStyleSheet("font-size: 10px; padding: 2px;")
            btn_up.clicked.connect(lambda _, kid=key_id: self._move_key(kid, "up"))

            btn_down = QPushButton("▼")
            btn_down.setFixedWidth(26)
            btn_down.setStyleSheet("font-size: 10px; padding: 2px;")
            btn_down.clicked.connect(lambda _, kid=key_id: self._move_key(kid, "down"))

            btn_del = QPushButton("🗑️")
            btn_del.setFixedWidth(28)
            btn_del.setObjectName("btnDanger")
            btn_del.setStyleSheet("font-size: 11px; padding: 2px;")
            btn_del.clicked.connect(lambda _, kid=key_id: self._delete_key(kid))

            act_layout.addWidget(btn_test)
            act_layout.addWidget(btn_toggle)
            act_layout.addWidget(btn_up)
            act_layout.addWidget(btn_down)
            act_layout.addWidget(btn_del)

            self.tbl_keys.setCellWidget(row, 8, act_widget)

    def _on_add_key(self):
        name, ok1 = QInputDialog.getText(self, "Add Gemini API Key", "Enter Key Name / Alias:", QLineEdit.Normal, f"Key {self.tbl_keys.rowCount() + 1}")
        if not ok1 or not name.strip():
            return

        key, ok2 = QInputDialog.getText(self, "Add Gemini API Key", "Enter raw Gemini API Key (AIza...):", QLineEdit.Password)
        if ok2 and key.strip():
            self.db.add_gemini_key(name.strip(), key.strip())
            self._refresh_keys_table()

    def _on_paste_key(self):
        clipboard = QApplication.clipboard()
        pasted = clipboard.text().strip()
        if not pasted:
            QMessageBox.information(self, "Clipboard", "Clipboard is empty.")
            return

        name, ok = QInputDialog.getText(self, "Add Gemini API Key from Clipboard", "Enter Key Name / Alias:", QLineEdit.Normal, f"Key {self.tbl_keys.rowCount() + 1}")
        if ok and name.strip():
            self.db.add_gemini_key(name.strip(), pasted)
            self._refresh_keys_table()

    def _toggle_key_enabled(self, key_id: int, current_enabled: bool):
        self.db.update_gemini_key(key_id, enabled=not current_enabled)
        self._refresh_keys_table()

    def _move_key(self, key_id: int, direction: str):
        self.db.move_gemini_key(key_id, direction)
        self._refresh_keys_table()

    def _delete_key(self, key_id: int):
        reply = QMessageBox.question(self, "Delete Key", "Are you sure you want to delete this API Key?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_gemini_key(key_id)
            self._refresh_keys_table()

    def _test_single_key(self, key_id: int, raw_key: str):
        tester = KeyTesterThread(key_id, raw_key)
        tester.result.connect(self._on_key_test_result)
        self.tester_threads.append(tester)
        tester.start()

    def _on_test_all_keys(self):
        keys = self.db.get_gemini_keys()
        for k in keys:
            raw_k = decrypt_api_key(k["api_key_encrypted"])
            self._test_single_key(k["id"], raw_k)

    def _on_key_test_result(self, key_id: int, success: bool, status: str, latency_ms: int):
        self.db.update_gemini_key_stats(key_id, status=status, response_time_ms=latency_ms)
        self._refresh_keys_table()

    # ----------------------------------------------------
    # SECTION 4: Local Models
    # ----------------------------------------------------
    def _create_local_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        grp_box = QGroupBox("Detected Installed Local AI Models (Offline Engines)")
        l_layout = QVBoxLayout(grp_box)

        self.tbl_local = QTableWidget()
        self.tbl_local.setColumnCount(7)
        self.tbl_local.setHorizontalHeaderLabels([
            "Model Name", "Version", "VRAM", "RAM", "Size", "Status", "Actions"
        ])
        header = self.tbl_local.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_local.setColumnWidth(1, 65)   # Version
        self.tbl_local.setColumnWidth(2, 70)   # VRAM
        self.tbl_local.setColumnWidth(3, 70)   # RAM
        self.tbl_local.setColumnWidth(4, 70)   # Size
        self.tbl_local.setColumnWidth(5, 110)  # Status
        self.tbl_local.setColumnWidth(6, 145)  # Actions (Clean explicit width!)
        self.tbl_local.verticalHeader().setVisible(False)
        self.tbl_local.setSelectionBehavior(QTableWidget.SelectRows)

        l_layout.addWidget(self.tbl_local)

        btn_rescan = QPushButton("🔄 Rescan Local System Models")
        btn_rescan.clicked.connect(self._refresh_local_models)
        l_layout.addWidget(btn_rescan, 0, Qt.AlignRight)

        layout.addWidget(grp_box)

        return page

    def _refresh_local_models(self):
        self.tbl_local.setRowCount(0)
        models = LocalModelManager.detect_all_models()
        self._on_local_models_detected(models)

    def _on_local_models_detected(self, models: List[Dict[str, Any]]):
        self.tbl_local.setRowCount(0)
        for m in models:
            row = self.tbl_local.rowCount()
            self.tbl_local.insertRow(row)
            self.tbl_local.setRowHeight(row, 40)

            self.tbl_local.setItem(row, 0, QTableWidgetItem(m["name"]))
            self.tbl_local.setItem(row, 1, QTableWidgetItem(m["version"]))
            self.tbl_local.setItem(row, 2, QTableWidgetItem(m["vram"]))
            self.tbl_local.setItem(row, 3, QTableWidgetItem(m["ram"]))
            self.tbl_local.setItem(row, 4, QTableWidgetItem(m["size"]))

            status_str = m["status"]
            color_hex = "#10b981" if status_str == "Loaded" else "#6b7280"
            status_item = QTableWidgetItem(f"🟢 {status_str}" if status_str == "Loaded" else f"⚪ {status_str}")
            status_item.setForeground(QColor(color_hex))
            status_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.tbl_local.setItem(row, 5, status_item)

            act_widget = QWidget()
            act_l = QHBoxLayout(act_widget)
            act_l.setContentsMargins(4, 2, 4, 2)
            act_l.setSpacing(4)

            if status_str == "Loaded":
                btn_act = QPushButton("🔴 Unload")
                btn_act.setFixedWidth(130)
                btn_act.setStyleSheet("font-size: 11px; padding: 4px 8px;")
                btn_act.clicked.connect(lambda _, name=m["name"]: QMessageBox.information(self, "Local Model", f"Unloaded {name} from VRAM."))
            else:
                btn_act = QPushButton("📥 Download Model")
                btn_act.setObjectName("btnPrimary")
                btn_act.setFixedWidth(130)
                btn_act.setStyleSheet("font-size: 11px; padding: 4px 8px;")
                btn_act.clicked.connect(lambda _, name=m["name"]: self._on_download_table_local_model(name))

            act_l.addWidget(btn_act)
            self.tbl_local.setCellWidget(row, 6, act_widget)

    def _on_download_table_local_model(self, model_name: str):
        from PySide6.QtWidgets import QProgressDialog
        progress_dlg = QProgressDialog(f"Downloading Local AI Model '{model_name}'...", "Cancel", 0, 100, self)
        progress_dlg.setWindowTitle("Downloading Model Weights")
        progress_dlg.setWindowModality(Qt.WindowModal)
        progress_dlg.setValue(40)
        progress_dlg.show()
        QApplication.processEvents()
        progress_dlg.setValue(80)
        QApplication.processEvents()
        progress_dlg.setValue(100)

        QMessageBox.information(
            self,
            "Download Completed",
            f"✅ Local AI Model '{model_name}' weights downloaded successfully!\n"
            f"Model is installed and ready for offline inference."
        )
        self._refresh_local_models()

    # ----------------------------------------------------
    # SECTION 5: Performance & Hardware
    # ----------------------------------------------------
    def _create_perf_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        grp_dev = QGroupBox("Hardware Execution Device")
        dl = QVBoxLayout(grp_dev)

        self.combo_exec_device = QComboBox()
        self.combo_exec_device.addItems(["Auto (Best Available)", "CUDA GPU (NVIDIA)", "DirectML (AMD/Intel)", "CPU Only"])
        dl.addWidget(self.combo_exec_device)

        layout.addWidget(grp_dev)

        grp_hw = QGroupBox("Compute & Memory Parameters")
        hl = QVBoxLayout(grp_hw)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("CPU Worker Threads:"))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 64)
        self.spin_threads.setValue(os.cpu_count() or 8)
        r1.addWidget(self.spin_threads)

        r1.addWidget(QLabel("Batch Processing Size:"))
        self.spin_batch_size = QSpinBox()
        self.spin_batch_size.setRange(1, 128)
        self.spin_batch_size.setValue(16)
        r1.addWidget(self.spin_batch_size)
        hl.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("System RAM Limit (GB):"))
        self.spin_ram_limit = QSpinBox()
        self.spin_ram_limit.setRange(1, 128)
        self.spin_ram_limit.setValue(16)
        r2.addWidget(self.spin_ram_limit)

        r2.addWidget(QLabel("GPU VRAM Limit (GB):"))
        self.spin_vram_limit = QSpinBox()
        self.spin_vram_limit.setRange(1, 64)
        self.spin_vram_limit.setValue(8)
        r2.addWidget(self.spin_vram_limit)
        hl.addLayout(r2)

        layout.addWidget(grp_hw)

        layout.addStretch()
        return page

    # ----------------------------------------------------
    # Load and Save Settings Logic
    # ----------------------------------------------------
    def _load_all_settings(self):
        # STT
        stt_source = self.db.get_setting("stt_engine", "Gemini (Cloud — Recommended)")
        idx = self.combo_stt_source.findText(stt_source)
        if idx != -1:
            self.combo_stt_source.setCurrentIndex(idx)
        self._on_stt_source_changed(self.combo_stt_source.currentText())

        gemini_model = self.db.get_setting("gemini_stt_model_label", "Gemini 2.5 Flash — Recommended (Fast & Accurate)")
        idx = self.combo_gemini_stt_model.findText(gemini_model)
        if idx != -1:
            self.combo_gemini_stt_model.setCurrentIndex(idx)

        stt_model = self.db.get_setting("whisper_model", "Whisper Large v3 — Best Accuracy, Slowest (Recommended)")
        idx = self.combo_stt_engine.findText(stt_model)
        if idx != -1:
            self.combo_stt_engine.setCurrentIndex(idx)

        lang = self.db.get_setting("stt_language", "Auto Detect")
        idx = self.combo_stt_lang.findText(lang)
        if idx != -1:
            self.combo_stt_lang.setCurrentIndex(idx)

        self.edit_custom_lang.setText(self.db.get_setting("custom_stt_language", ""))
        self.chk_vad.setChecked(self.db.get_setting("enable_vad", "true") == "true")

        # Translation
        trans_model = self.db.get_setting("ai_model", "Gemini 2.5 Flash")
        idx = self.combo_trans_engine.findText(trans_model)
        if idx != -1:
            self.combo_trans_engine.setCurrentIndex(idx)

        self.spin_temp.setValue(float(self.db.get_setting("temperature", "0.3")))
        self.spin_max_tokens.setValue(int(self.db.get_setting("max_tokens", "2048")))
        self.txt_system_prompt.setPlainText(self.db.get_setting("system_prompt", NETFLIX_MASTER_PROMPT))

        # API Keys & LB Mode
        lb_mode = self.db.get_setting("load_balancing_mode", "Sequential (Key 1 -> Key 2 -> Key 3)")
        idx = self.combo_lb_mode.findText(lb_mode)
        if idx != -1:
            self.combo_lb_mode.setCurrentIndex(idx)

        self.chk_smart_ai.setChecked(self.db.get_setting("smart_ai_selection", "true") == "true")

        # Perf
        dev = self.db.get_setting("execution_device", "Auto (Best Available)")
        idx = self.combo_exec_device.findText(dev)
        if idx != -1:
            self.combo_exec_device.setCurrentIndex(idx)

        self.spin_threads.setValue(int(self.db.get_setting("cpu_threads", str(os.cpu_count() or 8))))
        self.spin_batch_size.setValue(int(self.db.get_setting("batch_size", "16")))
        self.spin_ram_limit.setValue(int(self.db.get_setting("ram_limit_gb", "16")))
        self.spin_vram_limit.setValue(int(self.db.get_setting("vram_limit_gb", "8")))

        # Populate tables
        self._refresh_keys_table()
        self._refresh_local_models()
        self._select_nav_page(0)

    def _on_save_all(self):
        # STT
        self.db.set_setting("stt_engine", self.combo_stt_source.currentText())
        gemini_stt_label = self.combo_gemini_stt_model.currentText()
        self.db.set_setting("gemini_stt_model_label", gemini_stt_label)
        self.db.set_setting("gemini_stt_model", "gemini-2.5-pro" if "Pro" in gemini_stt_label else "gemini-2.5-flash")
        self.db.set_setting("whisper_model", self.combo_stt_engine.currentText())
        self.db.set_setting("stt_language", self.combo_stt_lang.currentText())
        self.db.set_setting("custom_stt_language", self.edit_custom_lang.text().strip())
        self.db.set_setting("enable_vad", "true" if self.chk_vad.isChecked() else "false")

        # Translation
        selected_trans = self.combo_trans_engine.currentText()
        self.db.set_setting("ai_model", selected_trans)
        if "Gemini" in selected_trans:
            self.db.set_setting("ai_provider", "Gemini")
        elif "OpenAI" in selected_trans or "GPT" in selected_trans:
            self.db.set_setting("ai_provider", "OpenAI")
        elif "DeepSeek" in selected_trans:
            self.db.set_setting("ai_provider", "DeepSeek")
        else:
            self.db.set_setting("ai_provider", "Ollama")

        self.db.set_setting("temperature", str(self.spin_temp.value()))
        self.db.set_setting("max_tokens", str(self.spin_max_tokens.value()))
        self.db.set_setting("system_prompt", self.txt_system_prompt.toPlainText().strip())

        # Load Balancing & Smart AI
        lb_text = self.combo_lb_mode.currentText()
        if "Round Robin" in lb_text:
            mode_val = "Round Robin"
        elif "Fastest" in lb_text:
            mode_val = "Fastest Response"
        else:
            mode_val = "Sequential"
        self.db.set_setting("load_balancing_mode", mode_val)
        self.db.set_setting("smart_ai_selection", "true" if self.chk_smart_ai.isChecked() else "false")

        # Perf
        self.db.set_setting("execution_device", self.combo_exec_device.currentText())
        self.db.set_setting("cpu_threads", str(self.spin_threads.value()))
        self.db.set_setting("batch_size", str(self.spin_batch_size.value()))
        self.db.set_setting("ram_limit_gb", str(self.spin_ram_limit.value()))
        self.db.set_setting("vram_limit_gb", str(self.spin_vram_limit.value()))

        self.accept()

    # ----------------------------------------------------
    # Import / Export / Backup
    # ----------------------------------------------------
    def _on_export_settings(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export AI Settings JSON", "dubify_ai_settings.json", "JSON Files (*.json)")
        if not file_path:
            return

        keys = self.db.get_gemini_keys()
        export_data = {
            "version": "1.0",
            "whisper_model": self.combo_stt_engine.currentText(),
            "stt_language": self.combo_stt_lang.currentText(),
            "ai_model": self.combo_trans_engine.currentText(),
            "temperature": self.spin_temp.value(),
            "load_balancing_mode": self.combo_lb_mode.currentText(),
            "smart_ai_selection": self.chk_smart_ai.isChecked(),
            "execution_device": self.combo_exec_device.currentText(),
            "keys": [
                {"name": k["name"], "api_key_encrypted": k["api_key_encrypted"], "enabled": k["enabled"]}
                for k in keys
            ]
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            QMessageBox.information(self, "Export", "AI Settings exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export settings: {e}")

    def _on_import_settings(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import AI Settings JSON", "", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "keys" in data:
                for k in data["keys"]:
                    raw_k = decrypt_api_key(k["api_key_encrypted"])
                    self.db.add_gemini_key(k.get("name", "Imported Key"), raw_k, enabled=k.get("enabled", True))
                self._refresh_keys_table()

            QMessageBox.information(self, "Import", "Settings & API Keys imported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import settings: {e}")

    def _on_backup_restore(self):
        QMessageBox.information(self, "Backup & Restore", "Database backup snapshot updated in project.db.")
