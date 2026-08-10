import os
import sys
import shutil
import subprocess
import imageio_ffmpeg
from PySide6.QtWidgets import QApplication

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translator.app.core.ffmpeg import FFmpegManager
from translator.app.core.exporter import ExportManager
from translator.app.model.models import SubtitleItem

# Initialize Qt App for font metrics/rendering
app = QApplication(sys.argv)

# Paths
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
scratch_dir = os.path.abspath(os.path.dirname(__file__))
test_vid = os.path.join(scratch_dir, "test_in.mp4").replace("\\", "/")
out_vid = os.path.join(scratch_dir, "test_out.mp4").replace("\\", "/")
screenshot = os.path.join(scratch_dir, "test_result.png").replace("\\", "/")
artifact_dest = r"C:\Users\RPC\.gemini\antigravity-ide\brain\56ef8b75-cd85-4e98-972a-7db77973acbd\export_result.png"

# 1. Generate test video (blue screen with silent audio)
subprocess.run([
    ffmpeg_exe, "-y", 
    "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=1",
    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100:d=1",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", test_vid
], check=True)

# 2. Setup ExportManager
ffmpeg_mgr = FFmpegManager(ffmpeg_exe)
exporter = ExportManager(ffmpeg_mgr)

# 3. Create dummy subtitles
subtitles = [
    SubtitleItem(id=1, start_ms=0, end_ms=1000, src_text="Hello, how are you?", tgt_text="សួស្តី តើអ្នកសុខសប្បាយជាទេ?")
]

# 4. Create style config similar to user's screenshot
style_config = {
    "font_name": "Khmer OS Battambang",
    "font_size": 24, # Will scale up automatically
    "primary_color": "#FFFFFF",
    "outline_color": "#000000",
    "bg_color": "#12101B",
    "outline_width": 2,
    "shadow_width": 0,
    "bold": True,
    "italic": False,
    "use_bg_box": True,
    "alignment": "Bottom Center",
    "sub_x_pct": 0.50,
    "sub_y_pct": 0.85
}

# 5. Run Export
success = exporter.export_video(
    video_path=test_vid,
    subtitles=subtitles,
    output_video_path=out_vid,
    style_config=style_config,
    logo_config=None,
    blur_config=None,
    mute_original_audio=False,
    aspect_ratio="9:16 (Portrait)"
)

if not success:
    print(f"EXPORT FAILED! Error: {ffmpeg_mgr.last_error}")
    sys.exit(1)

# 6. Extract frame at 0.5s
subprocess.run([
    ffmpeg_exe, "-y", "-i", out_vid, "-ss", "0.5", "-vframes", "1", screenshot
], check=True)

# 7. Copy to artifacts directory
shutil.copyfile(screenshot, artifact_dest)
print("SUCCESS!")
