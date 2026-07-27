from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QColorDialog, QCheckBox, QGroupBox,
    QFormLayout, QDialogButtonBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from ..database.sqlite import DatabaseManager

class SubtitleStyleDialog(QDialog):
    style_changed = Signal(dict)

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Subtitle Style & Typography Customizer — Dubify Studio")
        self.resize(540, 530)

        # Style settings from DB
        self.font_name = self.db.get_setting("sub_font_name", "Khmer OS Battambang")
        self.font_size = int(self.db.get_setting("sub_font_size", "24"))
        self.primary_color = self.db.get_setting("sub_primary_color", "#FFFFFF")
        self.outline_color = self.db.get_setting("sub_outline_color", "#000000")
        self.bg_color = self.db.get_setting("sub_bg_color", "#1E1E2E")
        self.outline_width = int(self.db.get_setting("sub_outline_width", "2"))
        self.shadow_width = int(self.db.get_setting("sub_shadow_width", "1"))
        self.bold = self.db.get_setting("sub_bold", "true") == "true"
        self.italic = self.db.get_setting("sub_italic", "false") == "true"
        self.use_bg_box = self.db.get_setting("sub_use_bg_box", "false") == "true"
        self.alignment = self.db.get_setting("sub_alignment", "Bottom Center")

        self._init_ui()
        self._update_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form_group = QGroupBox("Subtitle Style Settings")
        form_layout = QFormLayout(form_group)

        # Caption Style Presets
        self.combo_preset_style = QComboBox()
        self.combo_preset_style.addItems([
            "Custom / Manual",
            "White Clean (Default)",
            "Subtitle Box (Yellow)",
            "TikTok Caption",
            "Movie Caption (Gold)",
            "Drama Caption",
            "Golden Preset",
            "Neon Glow (Cyan)",
            "Blue Neon",
            "Pink Neon",
            "Glow",
            "Outline"
        ])
        self.combo_preset_style.currentTextChanged.connect(self._on_preset_selected)
        form_layout.addRow(QLabel("🎨 Preset Style:"), self.combo_preset_style)

        # Font Name
        self.combo_font = QComboBox()
        self.combo_font.addItems([
            "Khmer OS Battambang", "Khmer OS Muol Light", "Khmer OS Siemreap",
            "Khmer OS System", "Hanuman", "Kantenah Khmer", "Segoe UI", "Arial", "Impact"
        ])
        self.combo_font.setCurrentText(self.font_name)
        form_layout.addRow(QLabel("Font Family:"), self.combo_font)

        # Font Size
        self.spin_size = QSpinBox()
        self.spin_size.setRange(12, 72)
        self.spin_size.setValue(self.font_size)
        form_layout.addRow(QLabel("Font Size:"), self.spin_size)

        # Primary Color
        color_layout = QHBoxLayout()
        self.btn_primary_color = QPushButton()
        self.btn_primary_color.setFixedWidth(60)
        self.btn_primary_color.setStyleSheet(f"background-color: {self.primary_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_primary_hex = QLabel(self.primary_color)
        color_layout.addWidget(self.btn_primary_color)
        color_layout.addWidget(self.lbl_primary_hex)
        color_layout.addStretch()
        form_layout.addRow(QLabel("Text Color:"), color_layout)

        # Outline Color & Thickness
        outline_layout = QHBoxLayout()
        self.btn_outline_color = QPushButton()
        self.btn_outline_color.setFixedWidth(60)
        self.btn_outline_color.setStyleSheet(f"background-color: {self.outline_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_outline_hex = QLabel(self.outline_color)
        outline_layout.addWidget(self.btn_outline_color)
        outline_layout.addWidget(self.lbl_outline_hex)
        outline_layout.addStretch()

        self.spin_outline_width = QSpinBox()
        self.spin_outline_width.setRange(0, 10)
        self.spin_outline_width.setValue(self.outline_width)
        outline_layout.addWidget(QLabel("Width:"))
        outline_layout.addWidget(self.spin_outline_width)

        form_layout.addRow(QLabel("Outline:"), outline_layout)

        # Background Box Settings
        bg_layout = QHBoxLayout()
        self.chk_bg_box = QCheckBox("Enable Box")
        self.chk_bg_box.setChecked(self.use_bg_box)

        self.btn_bg_color = QPushButton()
        self.btn_bg_color.setFixedWidth(60)
        self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_bg_hex = QLabel(self.bg_color)

        bg_layout.addWidget(self.chk_bg_box)
        bg_layout.addWidget(self.btn_bg_color)
        bg_layout.addWidget(self.lbl_bg_hex)
        bg_layout.addStretch()
        form_layout.addRow(QLabel("Background Box:"), bg_layout)

        # Formatting Checkboxes & Shadow Width
        style_cb_layout = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold")
        self.chk_bold.setChecked(self.bold)
        self.chk_italic = QCheckBox("Italic")
        self.chk_italic.setChecked(self.italic)
        style_cb_layout.addWidget(self.chk_bold)
        style_cb_layout.addWidget(self.chk_italic)

        self.spin_shadow = QSpinBox()
        self.spin_shadow.setRange(0, 8)
        self.spin_shadow.setValue(self.shadow_width)
        style_cb_layout.addWidget(QLabel("Shadow:"))
        style_cb_layout.addWidget(self.spin_shadow)
        style_cb_layout.addStretch()
        form_layout.addRow(QLabel("Formatting:"), style_cb_layout)

        # Alignment
        self.combo_align = QComboBox()
        self.combo_align.addItems(["Bottom Center", "Bottom Left", "Bottom Right", "Top Center", "Middle"])
        self.combo_align.setCurrentText(self.alignment)
        form_layout.addRow(QLabel("Alignment:"), self.combo_align)

        layout.addWidget(form_group)

        # Live Preview Panel
        preview_group = QGroupBox("Live Subtitle Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_box = QLabel("មានរឿងព្រេងនិទានថា ការធ្វើជាព្រះនាងមិនមែនអំពីការធ្វើជាស្តេចទេ។\n(Sample Subtitle Preview Text)")
        self.preview_box.setAlignment(Qt.AlignCenter)
        self.preview_box.setMinimumHeight(90)
        self.preview_box.setStyleSheet("background-color: #0b0a14; border: 1px solid #2e2b52; border-radius: 6px;")

        preview_layout.addWidget(self.preview_box)
        layout.addWidget(preview_group)

        # Save / Cancel Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # Signals for Live Preview
        self.combo_font.currentTextChanged.connect(self._update_preview)
        self.spin_size.valueChanged.connect(self._update_preview)
        self.spin_outline_width.valueChanged.connect(self._update_preview)
        self.spin_shadow.valueChanged.connect(self._update_preview)
        self.chk_bold.toggled.connect(self._update_preview)
        self.chk_italic.toggled.connect(self._update_preview)
        self.chk_bg_box.toggled.connect(self._update_preview)
        self.combo_align.currentTextChanged.connect(self._update_preview)
        self.btn_primary_color.clicked.connect(self._pick_primary_color)
        self.btn_outline_color.clicked.connect(self._pick_outline_color)
        self.btn_bg_color.clicked.connect(self._pick_bg_color)

    def _pick_primary_color(self):
        col = QColorDialog.getColor(QColor(self.primary_color), self, "Select Text Color")
        if col.isValid():
            self.primary_color = col.name()
            self.btn_primary_color.setStyleSheet(f"background-color: {self.primary_color}; border: 1px solid #ffffff; border-radius: 4px;")
            self.lbl_primary_hex.setText(self.primary_color)
            self._update_preview()

    def _pick_outline_color(self):
        col = QColorDialog.getColor(QColor(self.outline_color), self, "Select Outline Color")
        if col.isValid():
            self.outline_color = col.name()
            self.btn_outline_color.setStyleSheet(f"background-color: {self.outline_color}; border: 1px solid #ffffff; border-radius: 4px;")
            self.lbl_outline_hex.setText(self.outline_color)
            self._update_preview()

    def _pick_bg_color(self):
        col = QColorDialog.getColor(QColor(self.bg_color), self, "Select Background Box Color")
        if col.isValid():
            self.bg_color = col.name()
            self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color}; border: 1px solid #ffffff; border-radius: 4px;")
            self.lbl_bg_hex.setText(self.bg_color)
            self._update_preview()

    def _on_preset_selected(self, preset_name: str):
        if "White Clean" in preset_name:
            self.primary_color = "#FFFFFF"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(2)
            self.spin_shadow.setValue(1)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(False)
        elif "Subtitle Box" in preset_name or "TikTok" in preset_name:
            self.primary_color = "#FDCE2A"
            self.outline_color = "#000000"
            self.bg_color = "#1E1E2E"
            self.spin_outline_width.setValue(0)
            self.spin_shadow.setValue(0)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(True)
        elif "Movie" in preset_name or "Gold" in preset_name:
            self.primary_color = "#FFD700"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(3)
            self.spin_shadow.setValue(2)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(False)
        elif "Neon" in preset_name and "Cyan" in preset_name:
            self.primary_color = "#00FFFF"
            self.outline_color = "#6C5CE7"
            self.spin_outline_width.setValue(4)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(False)
        elif "Blue Neon" in preset_name:
            self.primary_color = "#38BDF8"
            self.outline_color = "#1E3A8A"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(False)
        elif "Pink Neon" in preset_name:
            self.primary_color = "#FF007F"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(False)
        elif "Glow" in preset_name:
            self.primary_color = "#FACC15"
            self.outline_color = "#7C2D12"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)
            self.chk_bg_box.setChecked(False)

        self.btn_primary_color.setStyleSheet(f"background-color: {self.primary_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_primary_hex.setText(self.primary_color)
        self.btn_outline_color.setStyleSheet(f"background-color: {self.outline_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_outline_hex.setText(self.outline_color)
        self.btn_bg_color.setStyleSheet(f"background-color: {self.bg_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_bg_hex.setText(self.bg_color)
        self._update_preview()

    def get_style_config(self) -> dict:
        return {
            "font_name": self.combo_font.currentText(),
            "font_size": self.spin_size.value(),
            "primary_color": self.primary_color,
            "outline_color": self.outline_color,
            "bg_color": self.bg_color,
            "outline_width": self.spin_outline_width.value(),
            "shadow_width": self.spin_shadow.value(),
            "bold": self.chk_bold.isChecked(),
            "italic": self.chk_italic.isChecked(),
            "use_bg_box": self.chk_bg_box.isChecked(),
            "alignment": self.combo_align.currentText()
        }

    def _update_preview(self):
        cfg = self.get_style_config()
        self.style_changed.emit(cfg)

        font_name = cfg["font_name"]
        font_size = cfg["font_size"]
        bold_weight = "bold" if cfg["bold"] else "normal"
        italic_style = "italic" if cfg["italic"] else "normal"
        outline_w = cfg["outline_width"]
        sh_w = cfg["shadow_width"]
        bg_col = cfg["bg_color"] if cfg["use_bg_box"] else "#0b0a14"

        outline_css = ""
        if outline_w > 0:
            c = cfg["outline_color"]
            w = outline_w
            outline_css = f"text-shadow: -{w}px -{w}px 0 {c}, {w}px -{w}px 0 {c}, -{w}px {w}px 0 {c}, {w}px {w}px 0 {c};"

        style_str = f"""
            background-color: {bg_col};
            color: {cfg['primary_color']};
            font-family: '{font_name}', 'Segoe UI', sans-serif;
            font-size: {font_size}px;
            font-weight: {bold_weight};
            font-style: {italic_style};
            border: 1px solid #2e2b52;
            border-radius: 6px;
            padding: 10px;
            {outline_css}
        """
        self.preview_box.setStyleSheet(style_str)

    def _on_save(self):
        cfg = self.get_style_config()
        self.db.set_setting("sub_font_name", cfg["font_name"])
        self.db.set_setting("sub_font_size", str(cfg["font_size"]))
        self.db.set_setting("sub_primary_color", cfg["primary_color"])
        self.db.set_setting("sub_outline_color", cfg["outline_color"])
        self.db.set_setting("sub_bg_color", cfg["bg_color"])
        self.db.set_setting("sub_outline_width", str(cfg["outline_width"]))
        self.db.set_setting("sub_shadow_width", str(cfg["shadow_width"]))
        self.db.set_setting("sub_bold", "true" if cfg["bold"] else "false")
        self.db.set_setting("sub_italic", "true" if cfg["italic"] else "false")
        self.db.set_setting("sub_use_bg_box", "true" if cfg["use_bg_box"] else "false")
        self.db.set_setting("sub_alignment", cfg["alignment"])

        self.accept()
