from typing import List, Optional
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem
from ..ai.gemini import GeminiProvider

LANG_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}


class GeminiSTTWorker(QThread):
    """Cloud transcription via Gemini's audio understanding. Mirrors WhisperWorker's
    signal interface (progress/detected_language/finished/failed) so main_window can
    swap engines without branching downstream code."""
    progress = Signal(int, str)
    detected_language = Signal(str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, audio_path: str, model_name: str = "gemini-2.5-flash", language: Optional[str] = None, db=None):
        super().__init__()
        self.audio_path = audio_path
        self.model_name = model_name
        self.language = None if not language or language.lower().startswith("auto") else language
        self.db = db

    def run(self):
        try:
            self.progress.emit(5, f"Preparing Gemini STT ({self.model_name})...")
            provider = GeminiProvider(model_name=self.model_name, db=self.db)

            lang_hint = LANG_NAMES.get(self.language, self.language) if self.language else None
            segments = provider.transcribe_audio(
                self.audio_path,
                language=lang_hint,
                progress_cb=lambda pct, msg: self.progress.emit(pct, msg)
            )

            self.detected_language.emit(self.language or "zh")

            subtitles = []
            for idx, seg in enumerate(segments, 1):
                subtitles.append(SubtitleItem(
                    id=idx,
                    start_ms=seg["start_ms"],
                    end_ms=seg["end_ms"],
                    src_text=seg["text"],
                    tgt_text="",
                    status="Pending"
                ))

            self.progress.emit(100, "Gemini Speech Recognition Complete!")
            self.finished.emit(subtitles)

        except Exception as e:
            self.failed.emit(str(e))
