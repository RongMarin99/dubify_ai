import os
import subprocess
import imageio_ffmpeg

video_path = r"F:\videos\Snapfy\The Daughter They Buried Came Back - EP 01.mp4"
temp_wav = os.path.abspath(r"f:\project\dubify ai\temp\test_extracted.wav")
os.makedirs(os.path.dirname(temp_wav), exist_ok=True)

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
print("FFmpeg path:", ffmpeg_path)

cmd = [
    ffmpeg_path, "-y",
    "-i", video_path,
    "-ar", "16000",
    "-ac", "1",
    "-vn",
    temp_wav
]

res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print("Return code:", res.returncode)
print("Extracted wav exists:", os.path.exists(temp_wav))
if os.path.exists(temp_wav):
    print("Extracted wav size:", os.path.getsize(temp_wav), "bytes")
