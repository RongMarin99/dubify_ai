import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from translator.app.core.ffmpeg import FFmpegManager
from translator.app.core.exporter import ExportManager
from translator.app.model.models import SubtitleItem

def test_real_export():
    ffmpeg_mgr = FFmpegManager()
    exporter = ExportManager(ffmpeg_mgr)

    input_video = r"C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if not os.path.exists(input_video):
        print(f"Test video {input_video} not found, skipping real render test.")
        return

    out_video = os.path.abspath("temp/test_export_real_render.mp4")
    os.makedirs("temp", exist_ok=True)

    subtitles = [
        SubtitleItem(id=1, start_ms=0, end_ms=3000, src_text="Hello world", tgt_text="មិនអីទេ ស្អប់ខ្ញុំ Jason គឺជារមនុស្សល្ងង់ខ្លៅ", voice="Male 1")
    ]

    blur_cfg = {
        "x": 0.354,
        "y": 0.669,
        "w": 0.288,
        "h": 0.146,
        "enabled": True,
        "radius": 22,
        "color": "#0f0f19",
        "opacity": 0.85
    }

    style_cfg = {
        "font_name": "Khmer OS Battambang",
        "font_size": 24,
        "primary_color": "#FFFFFF",
        "outline_color": "#000000",
        "sub_y_pct": 0.85
    }

    print("Running REAL FFmpeg export test on sample video...")
    success = exporter.export_video(
        video_path=input_video,
        subtitles=subtitles,
        output_video_path=out_video,
        style_config=style_cfg,
        blur_config=blur_cfg,
        aspect_ratio="9:16 (Portrait)",
        mute_original_audio=False
    )

    print(f"FFmpeg Export Success: {success}")
    if not success:
        print(f"FFmpeg Last Error: {ffmpeg_mgr.last_error}")

    assert success, f"FFmpeg Render failed! Error: {ffmpeg_mgr.last_error}"
    assert os.path.exists(out_video) and os.path.getsize(out_video) > 0, "Output video file is missing or 0 bytes!"
    print("✓ REAL FFmpeg Export Test Passed 100%!")

if __name__ == "__main__":
    test_real_export()
