import shutil
import os
import sys

print("shutil.which('ffmpeg'):", shutil.which("ffmpeg"))
print("PATH environment:")
for p in os.environ.get("PATH", "").split(os.path.pathsep):
    if os.path.exists(os.path.join(p, "ffmpeg.exe")):
        print("Found ffmpeg.exe in:", p)

try:
    import imageio_ffmpeg
    print("imageio_ffmpeg exe path:", imageio_ffmpeg.get_ffmpeg_exe())
except ImportError:
    print("imageio_ffmpeg not installed")
