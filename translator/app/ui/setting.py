from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit,
    QPushButton, QDialogButtonBox, QFormLayout, QCheckBox, QFileDialog
)
from ..database.sqlite import DatabaseManager
from ..ai.gemini import NETFLIX_MASTER_PROMPT

class SettingsDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Dubify Studio - Preferences & AI Settings")
        self.resize(550, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # Tab 1: AI Provider & API
        tab_ai = QWidget()
        form_ai = QFormLayout(tab_ai)

        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["Gemini", "OpenAI", "DeepSeek", "Ollama", "Google Translate"])
        current_provider = self.db.get_setting("ai_provider", "Gemini")
        self.combo_provider.setCurrentText(current_provider)

        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.Password)
        self.edit_api_key.setText(self.db.get_setting("gemini_api_key", ""))

        # Model Select Dropdown (QComboBox Select)
        self.combo_model = QComboBox()
        self.combo_model.setEditable(False)
        self._update_model_options(current_provider)
        
        saved_model = self.db.get_setting("ai_model", "gemini-2.5-flash")
        if saved_model and self.combo_model.findText(saved_model) != -1:
            self.combo_model.setCurrentText(saved_model)

        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.1)
        self.spin_temp.setValue(float(self.db.get_setting("temperature", "0.3")))

        self.text_prompt = QTextEdit()
        self.text_prompt.setPlainText(self.db.get_setting("system_prompt", NETFLIX_MASTER_PROMPT))

        form_ai.addRow(QLabel("AI Provider:"), self.combo_provider)
        form_ai.addRow(QLabel("API Key:"), self.edit_api_key)
        form_ai.addRow(QLabel("Model Name:"), self.combo_model)
        form_ai.addRow(QLabel("Temperature:"), self.spin_temp)
        form_ai.addRow(QLabel("Drama Custom Prompt:"), self.text_prompt)

        self.tabs.addTab(tab_ai, "AI Translation Engine")

        # Tab 2: TTS Engine (CosyVoice 2 / VoxcM2 / Edge TTS)
        tab_tts = QWidget()
        form_tts = QFormLayout(tab_tts)

        self.combo_tts_engine = QComboBox()
        self.combo_tts_engine.addItems(["CosyVoice 2 / VoxcM2", "Edge TTS"])
        self.combo_tts_engine.setCurrentText(self.db.get_setting("tts_engine", "CosyVoice 2 / VoxcM2"))

        self.edit_cosyvoice_url = QLineEdit()
        self.edit_cosyvoice_url.setText(self.db.get_setting("cosyvoice_url", "http://localhost:50000/tts"))
        self.edit_cosyvoice_url.setPlaceholderText("http://localhost:50000/tts")

        form_tts.addRow(QLabel("TTS Engine Provider:"), self.combo_tts_engine)
        form_tts.addRow(QLabel("CosyVoice 2 / VoxcM2 API URL:"), self.edit_cosyvoice_url)

        self.tabs.addTab(tab_tts, "TTS Voice Dubbing Engine")

        # Tab 3: Speech-to-Text (Whisper)
        tab_stt = QWidget()
        form_stt = QFormLayout(tab_stt)

        self.combo_whisper_model = QComboBox()
        self.combo_whisper_model.addItems(["tiny", "base", "medium", "large-v3"])
        self.combo_whisper_model.setCurrentText(self.db.get_setting("whisper_model", "base"))

        self.combo_device = QComboBox()
        self.combo_device.addItems(["CPU", "GPU (CUDA)"])
        self.combo_device.setCurrentText(self.db.get_setting("whisper_device", "CPU"))

        self.chk_vad = QCheckBox("Enable VAD Voice Activity Filter")
        self.chk_vad.setChecked(self.db.get_setting("enable_vad", "true") == "true")

        form_stt.addRow(QLabel("Whisper Model:"), self.combo_whisper_model)
        form_stt.addRow(QLabel("Compute Device:"), self.combo_device)
        form_stt.addRow(QLabel("Options:"), self.chk_vad)

        self.tabs.addTab(tab_stt, "Speech Recognition (STT)")

        # Tab 4: System & FFmpeg
        tab_sys = QWidget()
        form_sys = QFormLayout(tab_sys)

        self.edit_ffmpeg = QLineEdit()
        self.edit_ffmpeg.setText(self.db.get_setting("ffmpeg_path", "ffmpeg"))

        self.edit_output = QLineEdit()
        self.edit_output.setText(self.db.get_setting("output_dir", "output"))

        form_sys.addRow(QLabel("FFmpeg Path:"), self.edit_ffmpeg)
        form_sys.addRow(QLabel("Default Output Folder:"), self.edit_output)

        self.tabs.addTab(tab_sys, "System & Paths")

        layout.addWidget(self.tabs)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # Signals
        self.combo_provider.currentTextChanged.connect(self._update_model_options)

    def _update_model_options(self, provider_name: str):
        self.combo_model.clear()
        if provider_name == "Gemini":
            self.combo_model.addItems([
                "gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.6-pro", "gemini-2.5-pro", "gemini-1.5-flash"
            ])
        elif provider_name == "OpenAI":
            self.combo_model.addItems(["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"])
        elif provider_name == "DeepSeek":
            self.combo_model.addItems(["deepseek-chat", "deepseek-reasoner"])
        elif provider_name == "Ollama":
            self.combo_model.addItems(["qwen2.5:7b", "llama3:8b", "deepseek-r1:8b"])
        else:
            self.combo_model.addItems(["default"])

    def _on_save(self):
        self.db.set_setting("ai_provider", self.combo_provider.currentText())
        self.db.set_setting("gemini_api_key", self.edit_api_key.text().strip())
        self.db.set_setting("ai_model", self.combo_model.currentText().strip())
        self.db.set_setting("temperature", str(self.spin_temp.value()))
        self.db.set_setting("system_prompt", self.text_prompt.toPlainText().strip())

        self.db.set_setting("tts_engine", self.combo_tts_engine.currentText())
        self.db.set_setting("cosyvoice_url", self.edit_cosyvoice_url.text().strip())

        self.db.set_setting("whisper_model", self.combo_whisper_model.currentText())
        self.db.set_setting("whisper_device", self.combo_device.currentText())
        self.db.set_setting("enable_vad", "true" if self.chk_vad.isChecked() else "false")

        self.db.set_setting("ffmpeg_path", self.edit_ffmpeg.text().strip())
        self.db.set_setting("output_dir", self.edit_output.text().strip())

        self.accept()
