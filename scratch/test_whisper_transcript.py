import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from app.core.whisper import WhisperWorker
from PySide6.QtCore import QCoreApplication

app = QCoreApplication(sys.argv)

wav_path = os.path.abspath(r"f:\project\dubify ai\temp\test_extracted.wav")
print(f"Testing Whisper Speech-To-Text transcription on: {wav_path}")

worker = WhisperWorker(audio_path=wav_path, model_size="base", language="zh")

def on_progress(pct, msg):
    print(f"[{pct}%] {msg}")

def on_finished(subtitles):
    print(f"\nSUCCESS! Generated {len(subtitles)} subtitle items:")
    for sub in subtitles[:10]:
        print(f"  [{sub.start_timecode} --> {sub.end_timecode}] {sub.src_text}")
    app.quit()

def on_failed(err):
    print(f"FAILED: {err}")
    app.quit()

worker.progress.connect(on_progress)
worker.finished.connect(on_finished)
worker.failed.connect(on_failed)
worker.start()

sys.exit(app.exec())
