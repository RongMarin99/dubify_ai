import os
import re
import difflib
from typing import List
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem

KHMER_ASR_MODEL = "sengtha/whisper-base-khmer"
FLAG_THRESHOLD = 0.45  # similarity below this = likely mispronounced/garbled TTS line


def _normalize_khmer(text: str) -> str:
    """Strip whitespace/punctuation noise so ASR-vs-script comparison isn't
    thrown off by spacing or punctuation differences alone."""
    text = re.sub(r'[\s\.,!?។៕៖­]+', '', text or '')
    return text.strip()


class KhmerAudioQAWorker(QThread):
    """Re-transcribes each generated Khmer TTS clip with a Khmer ASR model and
    compares it back against the intended subtitle text — catches mispronounced,
    garbled, or silent TTS lines before export. Uses sengtha/whisper-base-khmer
    (openai/whisper-base fine-tuned on Khmer speech, CC-BY-SA-4.0)."""
    progress = Signal(int, str)
    item_checked = Signal(int, str, float, bool)  # sub_id, transcribed_text, similarity, flagged
    finished = Signal(list)  # list of flagged sub_ids
    failed = Signal(str)

    def __init__(self, subtitles: List[SubtitleItem]):
        super().__init__()
        self.subtitles = subtitles
        self._asr = None

    def run(self):
        try:
            checkable = [s for s in self.subtitles if s.audio_path and os.path.exists(s.audio_path)]
            if not checkable:
                self.failed.emit("No generated audio found to verify — run Generate Audio first.")
                return

            self.progress.emit(5, f"Loading Khmer ASR model ({KHMER_ASR_MODEL})...")
            try:
                from transformers import pipeline
            except ImportError:
                self.failed.emit("Missing dependency 'transformers' (and 'torch'). Run: pip install transformers torch")
                return

            self._asr = pipeline(
                "automatic-speech-recognition",
                model=KHMER_ASR_MODEL,
                chunk_length_s=30,
                generate_kwargs={"language": "km", "task": "transcribe"}
            )

            total = len(checkable)
            flagged_ids = []
            for idx, sub in enumerate(checkable):
                self.progress.emit(
                    5 + int((idx / total) * 90),
                    f"Verifying line {idx + 1}/{total}..."
                )
                try:
                    result = self._asr(sub.audio_path)
                    transcribed = (result.get("text") or "").strip()
                except Exception as e:
                    transcribed = ""
                    self.progress.emit(5 + int((idx / total) * 90), f"Line {idx + 1}/{total} failed: {e}")

                a = _normalize_khmer(transcribed)
                b = _normalize_khmer(sub.tgt_text)
                similarity = difflib.SequenceMatcher(None, a, b).ratio() if (a and b) else 0.0
                flagged = similarity < FLAG_THRESHOLD

                if flagged:
                    flagged_ids.append(sub.id)

                self.item_checked.emit(sub.id, transcribed, similarity, flagged)

            self.progress.emit(100, f"Voice verification complete — {len(flagged_ids)} line(s) flagged for review.")
            self.finished.emit(flagged_ids)

        except Exception as e:
            self.failed.emit(str(e))
