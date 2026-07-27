import os
import sys
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from translator.app.core.ffmpeg import FFmpegManager
from translator.app.model.models import SubtitleItem
from translator.app.core.subtitle import SubtitleParser

def test_fixed_export():
    ffmpeg = FFmpegManager()
    
    # 1. Input video (User's real capcut video or synthetic 1080x1908 video)
    video_in = "C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if not os.path.exists(video_in):
        os.makedirs("temp", exist_ok=True)
        video_in = "temp/test_1080x1908.mp4"
        cmd = [
            ffmpeg.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=1080x1908:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=4",
            "-c:v", "libx264", "-c:a", "aac", video_in
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 2. Input dubbed audio (24000Hz mono WAV matching VoxcM2 / TTS output)
    dubbed_audio = "temp/merged_dubbed_track.wav"
    if not os.path.exists(dubbed_audio):
        cmd = [
            ffmpeg.ffmpeg_path, "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=24000:duration=4",
            "-ar", "24000", "-ac", "1", dubbed_audio
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 3. Subtitles
    sub_path = "temp/export_sub.ass"
    subs = [
        SubtitleItem(id=1, start_ms=500, end_ms=2500, src_text="Hello World", tgt_text="សួស្តី ពិភពលោក"),
        SubtitleItem(id=2, start_ms=2800, end_ms=3800, src_text="Second Line", tgt_text="បន្ទាត់ទី២")
    ]
    SubtitleParser.export_ass(subs, sub_path, use_target=True)

    out_video = "temp/rendered_output_fixed.mp4"
    if os.path.exists(out_video):
        os.remove(out_video)

    print("Testing fixed video export...")
    success = ffmpeg.export_video_with_subtitles(
        video_path=video_in,
        subtitle_path=sub_path,
        output_video_path=out_video,
        dubbed_audio_path=dubbed_audio,
        mute_original_audio=True,
        subtitles=subs,
        orig_audio_vol_pct=20
    )

    print(f"Export Success: {success}")
    if not success:
        print(f"FFmpeg Last Error:\n{ffmpeg.last_error}")

if __name__ == "__main__":
    test_fixed_export()
