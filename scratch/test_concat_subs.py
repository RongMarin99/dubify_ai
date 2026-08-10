import os
import subprocess
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QApplication

app = QApplication([])

target_w, target_h = 1080, 1920
os.makedirs("temp_subs", exist_ok=True)

# Create a blank transparent image
blank = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
blank.fill(Qt.transparent)
blank.save("temp_subs/blank.png")

# Create subtitle 1
img1 = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
img1.fill(Qt.transparent)
painter = QPainter(img1)
painter.setRenderHint(QPainter.Antialiasing)
painter.setRenderHint(QPainter.TextAntialiasing)
painter.setFont(QFont("Arial", 40))
painter.setPen(Qt.white)
painter.drawText(QRectF(0, 0, target_w, target_h), Qt.AlignCenter, "Subtitle 1")
painter.end()
img1.save("temp_subs/sub_1.png")

# Create subtitle 2
img2 = QImage(target_w, target_h, QImage.Format_ARGB32_Premultiplied)
img2.fill(Qt.transparent)
painter = QPainter(img2)
painter.setRenderHint(QPainter.Antialiasing)
painter.setRenderHint(QPainter.TextAntialiasing)
painter.setFont(QFont("Arial", 40))
painter.setPen(Qt.white)
painter.drawText(QRectF(0, 0, target_w, target_h), Qt.AlignCenter, "Subtitle 2")
painter.end()
img2.save("temp_subs/sub_2.png")

# Write concat file
concat_path = "temp_subs/concat.txt"
with open(concat_path, "w", encoding="utf-8") as f:
    f.write("ffconcat version 1.0\n")
    # 0.0 to 1.0s gap
    f.write("file 'blank.png'\n")
    f.write("duration 1.0\n")
    # 1.0 to 3.0s Subtitle 1
    f.write("file 'sub_1.png'\n")
    f.write("duration 2.0\n")
    # 3.0 to 4.0s gap
    f.write("file 'blank.png'\n")
    f.write("duration 1.0\n")
    # 4.0 to 5.0s Subtitle 2
    f.write("file 'sub_2.png'\n")
    f.write("duration 1.0\n")
    # Must repeat the last file to ensure the duration is respected due to a quirk in concat demuxer
    f.write("file 'blank.png'\n")

import imageio_ffmpeg
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

# Now use ffmpeg to generate a test video
cmd = [
    ffmpeg_exe, "-y",
    "-f", "lavfi", "-i", f"color=c=black:s={target_w}x{target_h}:d=6",
    "-f", "concat", "-safe", "0", "-i", concat_path,
    "-filter_complex", "[0:v][1:v]overlay=0:0",
    "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "temp_subs/output.mp4"
]

print("Running FFmpeg...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print("SUCCESS!")
else:
    print("FFmpeg failed:")
    print(res.stderr)
