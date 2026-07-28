import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from translator.app.core.subtitle import SubtitleParser
from translator.app.model.models import SubtitleItem

subtitles = [
    SubtitleItem(id=1, start_ms=0, end_ms=3000, src_text="Hello world", tgt_text="មិនអីទេ ស្អប់ខ្ញុំ Jason គឺជាមនុស្សល្ងង់ខ្លៅ", voice="Male 1")
]

style_cfg = {
    "font_name": "Khmer OS Battambang",
    "font_size": 24,
    "primary_color": "#FFFFFF",
    "outline_color": "#000000",
    "sub_y_pct": 0.85
}

test_ass_path = os.path.abspath("temp/test_export_916.ass")
os.makedirs("temp", exist_ok=True)

SubtitleParser.export_ass(subtitles, test_ass_path, use_target=True, style_config=style_cfg, aspect_ratio="9:16 (Portrait)")

with open(test_ass_path, "r", encoding="utf-8") as f:
    content = f.read()

print("--- GENERATED ASS SUBTITLE FOR 9:16 EXPORT ---")
print(content[:500])

assert "PlayResX: 1080" in content, "Error: PlayResX is not 1080!"
assert "PlayResY: 1920" in content, "Error: PlayResY is not 1920!"
assert "Fontsize,64" in content or ",64," in content, "Error: Font size was not scaled up for 1080x1920!"

print("\n✓ ASS Subtitle Export Scaling Test Passed 100%!")
