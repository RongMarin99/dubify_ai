import re
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QInputDialog, QMessageBox,
    QDialog, QLabel, QComboBox, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QKeySequence, QShortcut, QFont
from ..model.models import SubtitleItem

FEMALE_KEYWORDS = [
    "小姐", "夫人", "少夫人", "丫鬟", "公主", "郡主", "娘娘", "皇后", "臣妾", "妹妹", "姐姐", 
    "妈妈", "阿姨", "女", "អ្នកនាង", "លោកស្រី", "ព្រះនាង", "ប្អូនស្រី", "ស្រី", "នាង"
]

MALE_KEYWORDS = [
    "少爷", "老爷", "侯爷", "总裁", "董事长", "皇上", "陛下", "微臣", "本王", "王爷", "师父", 
    "师兄", "师弟", "哥哥", "弟弟", "爸爸", "叔叔", "男", "លោកម្ចាស់", "លោក ហ៊ូ", "អគ្គនាយក", 
    "ប្រធានក្រុមហ៊ុន", "ប្រុស", "លោក"
]

def auto_detect_speaker_voice(src_text: str = "", tgt_text: str = "", default_male: str = "VoxcM2 Male 1", default_female: str = "VoxcM2 Female 1") -> str:
    """Intelligently detect speaker gender from Chinese and Khmer text and assign VoxcM2 voice profile."""
    combined = (src_text or "") + " " + (tgt_text or "")
    
    # 1. Check female keywords
    for kw in FEMALE_KEYWORDS:
        if kw in combined:
            return default_female
            
    # 2. Check male keywords
    for kw in MALE_KEYWORDS:
        if kw in combined:
            return default_male

    return default_male


class CharacterScanDialog(QDialog):
    def __init__(self, subtitles: List[SubtitleItem], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan Characters & Assign VoxcM2 Voices")
        self.resize(480, 340)
        self.subtitles = subtitles
        self.character_voices = {}

        self.layout = QVBoxLayout(self)

        info_lbl = QLabel("Scan subtitle text for character names/speakers and auto-assign VoxcM2 / CosyVoice 2 profiles:")
        info_lbl.setWordWrap(True)
        self.layout.addWidget(info_lbl)

        form_layout = QFormLayout()

        # Detected default roles
        self.roles = {
            "Male Lead (ប្រុស)": "VoxcM2 Male 1",
            "Female Lead (ស្រី)": "VoxcM2 Female 1",
            "Supporting Male (ប្រុសរង)": "VoxcM2 Male 2",
            "Supporting Female (ស្រីរង)": "VoxcM2 Female 2",
            "Elderly Man (លោកតា)": "Old Man",
            "Elderly Woman (លោកយាយ)": "Old Woman",
            "Child (កុមារ)": "Child"
        }

        self.combos = {}
        voice_options = [
            "VoxcM2 Male 1", "VoxcM2 Female 1", "VoxcM2 Male 2", "VoxcM2 Female 2",
            "Male 1", "Male 2", "Female 1", "Female 2", "Child", "Old Man", "Old Woman"
        ]
        for role, default_v in self.roles.items():
            combo = QComboBox()
            combo.addItems(voice_options)
            combo.setCurrentText(default_v)
            form_layout.addRow(QLabel(role), combo)
            self.combos[role] = combo

        self.layout.addLayout(form_layout)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        self.layout.addWidget(btn_box)

    def get_mappings(self):
        return {role: combo.currentText() for role, combo in self.combos.items()}


class SubtitleEditorWidget(QWidget):
    subtitle_changed = Signal()
    row_selected = Signal(int)  # ms timestamp of selected row
    style_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.subtitles: List[SubtitleItem] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Top Action Toolbar
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(6)

        self.btn_add = QPushButton("+ Add Text")
        self.btn_edit = QPushButton("Edit")
        self.btn_delete = QPushButton("Delete")
        self.btn_find = QPushButton("Find & Replace")
        self.btn_shift_time = QPushButton("⏱️ Shift Time")
        self.btn_style = QPushButton("🎨 Subtitle Style")
        self.btn_scan = QPushButton(" Scan Characters")
        self.btn_scan.setObjectName("PrimaryBtn")

        tb_layout.addWidget(self.btn_add)
        tb_layout.addWidget(self.btn_edit)
        tb_layout.addWidget(self.btn_delete)
        tb_layout.addWidget(self.btn_find)
        tb_layout.addWidget(self.btn_shift_time)
        tb_layout.addWidget(self.btn_style)
        tb_layout.addWidget(self.btn_scan)
        tb_layout.addStretch()

        layout.addLayout(tb_layout)

        # Subtitle Data QTableWidget
        self.table = QTableWidget()
        self.table.setFont(QFont("Khmer OS Battambang", 11))
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "START", "END", "CHINESE TEXT", "KHMER TEXT (EDITABLE)", "VOICE", "AUDIO STATUS"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.table)

        # Bottom hint label
        hint_lbl = QLabel("Double-click START / END / KHMER TEXT to edit, click VOICE to choose Male/Female, AUDIO to play.")
        hint_lbl.setStyleSheet("color: #7b78a8; font-size: 11px;")
        layout.addWidget(hint_lbl)

        # Connect Signals
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_find.clicked.connect(self._on_find_replace)
        self.btn_shift_time.clicked.connect(self._on_shift_time)
        self.btn_style.clicked.connect(self.style_clicked)
        self.btn_scan.clicked.connect(self._on_scan_characters)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_shift_time(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Warning", "No subtitles loaded to shift.")
            return

        options = [
            "+1.0s (Voice speaks 1.0s later)",
            "+0.5s (Voice speaks 0.5s later)",
            "-0.5s (Voice speaks 0.5s earlier)",
            "-1.0s (Voice speaks 1.0s earlier)",
            "-2.0s (Voice speaks 2.0s earlier)"
        ]
        item, ok = QInputDialog.getItem(self, "Shift Subtitle Timestamps", "Select timing offset to apply to all subtitles:", options, 0, False)
        if ok and item:
            shift_ms = 0
            if "+1.0s" in item: shift_ms = 1000
            elif "+0.5s" in item: shift_ms = 500
            elif "-0.5s" in item: shift_ms = -500
            elif "-1.0s" in item: shift_ms = -1000
            elif "-2.0s" in item: shift_ms = -2000

            for sub in self.subtitles:
                sub.start_ms = max(0, sub.start_ms + shift_ms)
                sub.end_ms = max(1000, sub.end_ms + shift_ms)

            self.load_subtitles(self.subtitles)
            self.subtitle_changed.emit()
            QMessageBox.information(self, "Timestamps Shifted", f"Successfully shifted all subtitles by {item.split()[0]}.")

        # Keyboard shortcuts
        QShortcut(QKeySequence("Delete"), self, self._on_delete)
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_add)

    def load_subtitles(self, subtitles: List[SubtitleItem]):
        self.subtitles = subtitles
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for row, item in enumerate(subtitles):
            self.table.insertRow(row)

            # START
            start_item = QTableWidgetItem(item.start_timecode)

            # END
            end_item = QTableWidgetItem(item.end_timecode)

            # CHINESE / SOURCE TEXT
            src_item = QTableWidgetItem(item.src_text)

            # KHMER / TARGET TEXT (EDITABLE)
            tgt_item = QTableWidgetItem(item.tgt_text)

            # VOICE
            voice_item = QTableWidgetItem(item.voice)

            # AUDIO STATUS
            status_item = QTableWidgetItem(item.status)
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, start_item)
            self.table.setItem(row, 1, end_item)
            self.table.setItem(row, 2, src_item)
            self.table.setItem(row, 3, tgt_item)
            self.table.setItem(row, 4, voice_item)
            self.table.setItem(row, 5, status_item)

        self.table.blockSignals(False)

    def get_subtitles(self) -> List[SubtitleItem]:
        return self.subtitles

    def update_single_translation(self, sub_id: int, tgt_text: str):
        for row, item in enumerate(self.subtitles):
            if item.id == sub_id:
                item.tgt_text = tgt_text
                item.status = "Translated"
                self.table.blockSignals(True)
                if self.table.item(row, 3):
                    self.table.item(row, 3).setText(tgt_text)
                if self.table.item(row, 5):
                    self.table.item(row, 5).setText("Translated")
                self.table.blockSignals(False)
                break

    def _on_cell_changed(self, row: int, col: int):
        if row < 0 or row >= len(self.subtitles):
            return

        item = self.subtitles[row]
        cell_item = self.table.item(row, col)
        if not cell_item:
            return

        val = cell_item.text()
        if col == 0:  # Start
            item.start_ms = SubtitleItem.timecode_to_ms(val)
        elif col == 1:  # End
            item.end_ms = SubtitleItem.timecode_to_ms(val)
        elif col == 2:  # Chinese
            item.src_text = val
        elif col == 3:  # Khmer
            item.tgt_text = val
        elif col == 4:  # Voice
            item.voice = val

        self.subtitle_changed.emit()

    def _on_selection_changed(self):
        selected_rows = self.table.selectedIndexes()
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self.subtitles):
                self.row_selected.emit(self.subtitles[row].start_ms)

    def _on_add(self):
        row = self.table.currentRow()
        start_ms = 0
        if row >= 0 and row < len(self.subtitles):
            start_ms = self.subtitles[row].end_ms + 100
        end_ms = start_ms + 3000

        new_sub = SubtitleItem(
            id=len(self.subtitles) + 1,
            start_ms=start_ms,
            end_ms=end_ms,
            src_text="New Chinese Text",
            tgt_text="",
            status="Pending"
        )
        self.subtitles.append(new_sub)
        self.load_subtitles(self.subtitles)
        self.subtitle_changed.emit()

    def _on_edit(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.editItem(self.table.item(row, 3))

    def _on_delete(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.subtitles):
            del self.subtitles[row]
            self.load_subtitles(self.subtitles)
            self.subtitle_changed.emit()

    def _on_find_replace(self):
        target, ok = QInputDialog.getText(self, "Find & Replace", "Enter text to replace:")
        if ok and target:
            replacement, ok2 = QInputDialog.getText(self, "Find & Replace", f"Replace '{target}' with:")
            if ok2:
                count = 0
                for item in self.subtitles:
                    if target in item.tgt_text:
                        item.tgt_text = item.tgt_text.replace(target, replacement)
                        count += 1
                self.load_subtitles(self.subtitles)
                QMessageBox.information(self, "Replaced", f"Replaced {count} occurrences.")
                self.subtitle_changed.emit()

    def _on_scan_characters(self):
        if not self.subtitles:
            QMessageBox.warning(self, "Warning", "No subtitles loaded to scan.")
            return

        dlg = CharacterScanDialog(self.subtitles, self)
        if dlg.exec() == QDialog.Accepted:
            mappings = dlg.get_mappings()
            def_male = mappings.get("Male Lead (ប្រុស)", "VoxcM2 Male 1")
            def_female = mappings.get("Female Lead (ស្រី)", "VoxcM2 Female 1")

            male_cnt = 0
            female_cnt = 0

            for item in self.subtitles:
                detected_v = auto_detect_speaker_voice(item.src_text, item.tgt_text, def_male, def_female)
                item.voice = detected_v
                if "Female" in detected_v or "ស្រី" in detected_v:
                    female_cnt += 1
                else:
                    male_cnt += 1

            self.load_subtitles(self.subtitles)
            QMessageBox.information(
                self, "VoxcM2 Character Detection Complete",
                f"Scanned character text and assigned VoxcM2 / CosyVoice 2 voices:\n\n"
                f"• Male Voices ({def_male}): {male_cnt} lines\n"
                f"• Female Voices ({def_female}): {female_cnt} lines"
            )
            self.subtitle_changed.emit()
