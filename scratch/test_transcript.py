import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from app.core.ffmpeg import FFmpegManager
from app.core.whisper import WhisperWorker
from PySide6.QtCore import QCoreApplication

video_path = r"F:/videos/Snapfy/The Daughter They Buried Came Back - EP 01.mp4"
temp_wav = os.path.join(os.path.dirname(__file__), "..", "temp", "test_extracted.wav")
os.makedirs(os.path.dirname(temp_wav), exist_ok=True)

print(f"Testing video audio extraction for: {video_path}")
ffmpeg_mgr = FFmpegManager()
if ffmpeg_mgr.extract_audio(video_path, temp_wav):
    print(f"Audio extracted successfully: {temp_wav}")
    print(f"File size: {os.path.getsize(temp_wav)} bytes")
else:
    print("Audio extraction failed!")
