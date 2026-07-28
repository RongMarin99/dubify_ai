import sys
import os
import re

sys.stdout.reconfigure(encoding='utf-8')

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontMetrics
from translator.app.ui.overlay_canvas import wrap_text_to_pixel_width
from translator.app.ai.gemini import clean_khmer_translation

app = QApplication.instance() or QApplication(sys.argv)

print("--- TESTING KHMER TRANSLATION CLEANING ---")
raw_input = "អ្នកមិនដែលដាក់ចេញទេ។ ខ្ញុំគិតថាខ្ញុំនឹងរកប្រាក់បានខ្លះពីអ្វីដែលខ្ញុំមិនបានទទួល។ ល។"
cleaned = clean_khmer_translation(raw_input)
print(f"RAW INPUT  : {raw_input}")
print(f"CLEANED    : {cleaned}")
assert "។" not in cleaned and "." not in cleaned, "Error: Punctuation was not removed!"
print("✓ Khmer Translation cleaning test passed!")

print("\n--- TESTING 9:16 PIXEL LINE WRAPPING ---")
font = QFont("Khmer OS Battambang", 24)
metrics = QFontMetrics(font)

# Simulated 9:16 container frame width (e.g. 240px active frame width)
max_frame_px = 240.0 - 32.0  # minus padding

lines = wrap_text_to_pixel_width(cleaned, metrics, max_frame_px)
print(f"Max allowed line width: {max_frame_px}px")
print(f"Wrapped into {len(lines)} lines:")
for idx, line in enumerate(lines, 1):
    w = metrics.horizontalAdvance(line)
    print(f"  Line {idx} ({w}px <= {max_frame_px}px): '{line}'")
    assert w <= max_frame_px, f"Line {idx} ({w}px) exceeded max_frame_px ({max_frame_px}px)!"

print("✓ ALL 9:16 Pixel Line Wrapping tests passed 100%!")
