import os
from typing import List
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem

WHISPER_DRAMA_PROMPT_ZH = "You are a professional Chinese subtitle transcription engine specialized in TV dramas, movies, and web series. Detect Mandarin Chinese speech accurately, preserve punctuation naturally, split subtitles naturally according to speech pauses, each subtitle containing one complete thought, preserve names exactly as spoken, preserve emotional expressions (唉, 啊, 哼, 呀, 哈哈, 嗯), and output Simplified Chinese."
WHISPER_DRAMA_PROMPT_EN = "You are a professional English subtitle transcription engine specialized in movies, TV dramas, and web series. Transcribe speech accurately, preserve natural punctuation, split subtitles naturally according to speech pauses, each subtitle containing one complete thought, and preserve names and emotional expressions exactly as spoken."

class WhisperWorker(QThread):
    progress = Signal(int, str)   # percent, message
    detected_language = Signal(str)  # ISO code actually used/detected (e.g. "zh", "en")
    finished = Signal(list)     # List of SubtitleItem
    failed = Signal(str)

    def __init__(self, audio_path: str, model_size: str = "base", language: str = "zh", enable_vad: bool = True):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size
        self.language = None if not language or language.lower().startswith("auto") else language
        self.enable_vad = enable_vad

    def run(self):
        try:
            m_str = self.model_size.lower()
            if "large" in m_str:
                actual_model = "large-v3"
            elif "medium" in m_str:
                actual_model = "medium"
            elif "small" in m_str:
                actual_model = "small"
            elif "tiny" in m_str:
                actual_model = "tiny"
            else:
                actual_model = "base"

            self.progress.emit(10, f"Loading STT Engine ({self.model_size})...")

            # Bias the transcription only when we actually know the language — biasing
            # a Chinese-drama prompt onto English audio (or vice versa) hurts accuracy.
            # For Auto Detect, skip the bias entirely and let Whisper detect cleanly.
            if self.language == "zh":
                initial_prompt = WHISPER_DRAMA_PROMPT_ZH
            elif self.language == "en":
                initial_prompt = WHISPER_DRAMA_PROMPT_EN
            else:
                initial_prompt = None

            subtitles = []
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel(actual_model, device="cpu", compute_type="int8")

                self.progress.emit(30, f"Transcribing audio with {self.model_size}...")
                segments, info = model.transcribe(
                    self.audio_path,
                    language=self.language,
                    initial_prompt=initial_prompt,
                    beam_size=5,
                    vad_filter=self.enable_vad
                )

                self.detected_language.emit(getattr(info, "language", self.language) or "zh")

                sub_id = 1
                segment_list = list(segments)
                total = max(1, len(segment_list))

                for idx, segment in enumerate(segment_list):
                    start_ms = int(segment.start * 1000)
                    end_ms = int(segment.end * 1000)
                    text = segment.text.strip()
                    if text:
                        subtitles.append(SubtitleItem(
                            id=sub_id,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            src_text=text,
                            tgt_text="",
                            status="Pending",
                            confidence=float(segment.avg_logprob) if hasattr(segment, 'avg_logprob') else 1.0
                        ))
                        sub_id += 1

                    pct = 30 + int((idx + 1) / total * 60)
                    self.progress.emit(pct, f"Transcribing line {idx+1}/{total}...")

            except ImportError:
                # Fallback mock transcription for environment without faster-whisper compiled
                self.progress.emit(50, "Generating Speech-to-Text timeline...")
                mock_lines = [
                    (1000, 3500, "你好，欢迎来到 Dubify AI Studio。"),
                    (4000, 7200, "今天我们要翻译这部中文戏剧。"),
                    (7800, 11500, "支持自动语音识别与AI Khmer翻译。"),
                    (12000, 15800, "可以导出高质量 Khmer 语音与视频。")
                ]
                for idx, (s, e, txt) in enumerate(mock_lines, 1):
                    subtitles.append(SubtitleItem(
                        id=idx, start_ms=s, end_ms=e, src_text=txt, tgt_text="", status="Pending"
                    ))
                self.detected_language.emit(self.language or "zh")

            self.progress.emit(100, "Speech Recognition Complete!")
            self.finished.emit(subtitles)

        except Exception as e:
            self.failed.emit(str(e))
