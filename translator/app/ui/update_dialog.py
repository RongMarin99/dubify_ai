from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit

from ..version import APP_VERSION, GITHUB_OWNER, GITHUB_REPO


class UpdateAvailableDialog(QDialog):
    """Shown when a newer GitHub release is found. Lets the user choose to update
    now, be reminded again next launch, or skip this specific version for good."""

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info = info
        self.result_action = "later"  # "now" | "later" | "skip"

        self.setWindowTitle("Dubify AI — Update Available")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl_title = QLabel(f"🚀 New Version Available: {info['tag']}")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #8ecfae;")
        layout.addWidget(lbl_title)

        lbl_current = QLabel(f"You're running {APP_VERSION}")
        lbl_current.setStyleSheet("color: #8c89b4;")
        layout.addWidget(lbl_current)

        lbl_whats_new = QLabel("What's new:")
        lbl_whats_new.setStyleSheet("font-weight: 600; margin-top: 6px;")
        layout.addWidget(lbl_whats_new)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(info.get("notes", "").strip() or "No release notes provided.")
        txt.setFixedHeight(160)
        layout.addWidget(txt)

        changelog_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{info['tag']}"
        lbl_link = QLabel(f'<a href="{changelog_url}" style="color:#8ecfae;">Full Changelog</a>')
        lbl_link.setOpenExternalLinks(True)
        layout.addWidget(lbl_link)

        btn_row = QHBoxLayout()
        self.btn_skip = QPushButton("Skip This Version")
        self.btn_later = QPushButton("Remind Me Later")
        self.btn_update_now = QPushButton("⬇ Update Now")
        self.btn_update_now.setObjectName("PrimaryBtn")

        btn_row.addWidget(self.btn_skip)
        btn_row.addWidget(self.btn_later)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_update_now)
        layout.addLayout(btn_row)

        self.btn_skip.clicked.connect(self._on_skip)
        self.btn_later.clicked.connect(self._on_later)
        self.btn_update_now.clicked.connect(self._on_update_now)

    def _on_skip(self):
        self.result_action = "skip"
        self.accept()

    def _on_later(self):
        self.result_action = "later"
        self.reject()

    def _on_update_now(self):
        self.result_action = "now"
        self.accept()
