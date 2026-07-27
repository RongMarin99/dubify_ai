import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from translator.app.core.ffmpeg import FFmpegManager
from translator.app.model.models import SubtitleItem
from translator.app.core.subtitle import SubtitleParser

def test_export():
    ffmpeg = FFmpegManager()
    
    # Check ffmpeg availability
    print(f"FFmpeg path: {ffmpeg.ffmpeg_path}")
    assert ffmpeg.is_available(), "FFmpeg is not available!"

    # Create dummy video input if needed or test dummy files
    os.makedirs("temp", exist_ok=True)
    sub_path = "temp/test_sub.ass"
    out_video = "temp/test_out.mp4"

    subs = [
        SubtitleItem(id=1, start_ms=1000, end_ms=3000, src_text="Hello", tgt_text="សួស្តី 1"),
        SubtitleItem(id=2, start_ms=3500, end_ms=6000, src_text="World", tgt_text="ពិភពលោក 2")
    ]
    SubtitleParser.export_ass(subs, sub_path, use_target=True)

    # Test export_video_with_subtitles with video if capcut video exists or create 5s synthetic video
    video_in = "C:/Users/RPC/Videos/capcut/0726 (1)(1).mp4"
    if not os.path.exists(video_in):
        video_in = "temp/test_input.mp4"
        import subprocess
        subprocess.run([ffmpeg.ffmpeg_path, "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=1080x1920:rate=30", "-f", "lavfi", "-i", "sine=frequency=1000:duration=5", "-c:v", "libx264", "-c:a", "aac", video_in], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    dubbed_audio = "temp/merged_dubbed_track.wav"
    if not os.path.exists(dubbed_audio):
        import subprocess
        subprocess.run([ffmpeg.ffmpeg_path, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", "-ar", "44100", "-ac", "2", dubbed_audio], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print(f"Testing export with video={video_in}, sub={sub_path}, dubbed={dubbed_audio}")
    success = ffmpeg.export_video_with_subtitles(
        video_path=video_in,
        subtitle_path=sub_path,
        output_video_path=out_video,
        dubbed_audio_path=dubbed_audio,
        mute_original_audio=True,
        subtitles=subs,
        orig_audio_vol_pct=20
    )

    print(f"Export result: {success}")
    if not success:
        print(f"FFmpeg Last Error:\n{ffmpeg.last_error}")

if __name__ == "__main__":
    test_export()
