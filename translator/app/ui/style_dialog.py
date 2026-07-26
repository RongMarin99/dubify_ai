from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QColorDialog, QCheckBox, QGroupBox,
    QFormLayout, QDialogButtonBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from ..database.sqlite import DatabaseManager

class SubtitleStyleDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Subtitle Style & Typography Customizer")
        self.resize(520, 480)

        # Default style settings from DB
        self.font_name = self.db.get_setting("sub_font_name", "Khmer OS Battambang")
        self.font_size = int(self.db.get_setting("sub_font_size", "24"))
        self.primary_color = self.db.get_setting("sub_primary_color", "#FFFFFF")
        self.outline_color = self.db.get_setting("sub_outline_color", "#000000")
        self.outline_width = int(self.db.get_setting("sub_outline_width", "2"))
        self.bold = self.db.get_setting("sub_bold", "true") == "true"
        self.italic = self.db.get_setting("sub_italic", "false") == "true"
        self.alignment = self.db.get_setting("sub_alignment", "Bottom Center")

        self._init_ui()
        self._update_preview()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Form Controls Group
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
            "Pink Neon"
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

        # Primary Color Button
        color_layout = QHBoxLayout()
        self.btn_primary_color = QPushButton()
        self.btn_primary_color.setFixedWidth(60)
        self.btn_primary_color.setStyleSheet(f"background-color: {self.primary_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_primary_hex = QLabel(self.primary_color)
        color_layout.addWidget(self.btn_primary_color)
        color_layout.addWidget(self.lbl_primary_hex)
        color_layout.addStretch()
        form_layout.addRow(QLabel("Text Color:"), color_layout)

        # Outline Color Button
        outline_layout = QHBoxLayout()
        self.btn_outline_color = QPushButton()
        self.btn_outline_color.setFixedWidth(60)
        self.btn_outline_color.setStyleSheet(f"background-color: {self.outline_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_outline_hex = QLabel(self.outline_color)
        outline_layout.addWidget(self.btn_outline_color)
        outline_layout.addWidget(self.lbl_outline_hex)
        outline_layout.addStretch()
        form_layout.addRow(QLabel("Outline Color:"), outline_layout)

        # Outline Width
        self.spin_outline_width = QSpinBox()
        self.spin_outline_width.setRange(0, 10)
        self.spin_outline_width.setValue(self.outline_width)
        form_layout.addRow(QLabel("Outline Thickness:"), self.spin_outline_width)

        # Font Styling Checkboxes
        style_cb_layout = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold")
        self.chk_bold.setChecked(self.bold)
        self.chk_italic = QCheckBox("Italic")
        self.chk_italic.setChecked(self.italic)
        style_cb_layout.addWidget(self.chk_bold)
        style_cb_layout.addWidget(self.chk_italic)
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
        self.chk_bold.toggled.connect(self._update_preview)
        self.chk_italic.toggled.connect(self._update_preview)
        self.btn_primary_color.clicked.connect(self._pick_primary_color)
        self.btn_outline_color.clicked.connect(self._pick_outline_color)

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

    def _on_preset_selected(self, preset_name: str):
        if "White Clean" in preset_name:
            self.primary_color = "#FFFFFF"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(2)
            self.chk_bold.setChecked(True)
        elif "Subtitle Box" in preset_name:
            self.primary_color = "#FDCE2A"
            self.outline_color = "#1E1E2E"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)
        elif "TikTok" in preset_name:
            self.primary_color = "#FDCE2A"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(4)
            self.chk_bold.setChecked(True)
        elif "Movie" in preset_name or "Gold" in preset_name:
            self.primary_color = "#FFD700"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)
        elif "Neon" in preset_name and "Cyan" in preset_name:
            self.primary_color = "#00FFFF"
            self.outline_color = "#6C5CE7"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)
        elif "Pink Neon" in preset_name:
            self.primary_color = "#FF007F"
            self.outline_color = "#000000"
            self.spin_outline_width.setValue(3)
            self.chk_bold.setChecked(True)

        self.btn_primary_color.setStyleSheet(f"background-color: {self.primary_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_primary_hex.setText(self.primary_color)
        self.btn_outline_color.setStyleSheet(f"background-color: {self.outline_color}; border: 1px solid #ffffff; border-radius: 4px;")
        self.lbl_outline_hex.setText(self.outline_color)
        self._update_preview()

    def _update_preview(self):
        font_name = self.combo_font.currentText()
        font_size = self.spin_size.value()
        bold_weight = "bold" if self.chk_bold.isChecked() else "normal"
        italic_style = "italic" if self.chk_italic.isChecked() else "normal"
        outline_w = self.spin_outline_width.value()

        # Generate CSS text stroke or shadow preview
        outline_css = ""
        if outline_w > 0:
            c = self.outline_color
            w = outline_w
            outline_css = f"text-shadow: -{w}px -{w}px 0 {c}, {w}px -{w}px 0 {c}, -{w}px {w}px 0 {c}, {w}px {w}px 0 {c};"

        style_str = f"""
            background-color: #0b0a14;
            color: {self.primary_color};
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
        self.db.set_setting("sub_font_name", self.combo_font.currentText())
        self.db.set_setting("sub_font_size", str(self.spin_size.value()))
        self.db.set_setting("sub_primary_color", self.primary_color)
        self.db.set_setting("sub_outline_color", self.outline_color)
        self.db.set_setting("sub_outline_width", str(self.spin_outline_width.value()))
        self.db.set_setting("sub_bold", "true" if self.chk_bold.isChecked() else "false")
        self.db.set_setting("sub_italic", "true" if self.chk_italic.isChecked() else "false")
        self.db.set_setting("sub_alignment", self.combo_align.currentText())

        self.accept()
