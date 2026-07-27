import os
import sys

# Add translator to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from translator.app.model.models import SubtitleItem
from translator.app.core.subtitle import SubtitleParser

def test_subtitle_preview_and_ass():
    print("=== 1. Testing Subtitle Time Range Lookup ===")
    subtitles = [
        SubtitleItem(id=1, start_ms=1000, end_ms=3000, src_text="Hello", tgt_text="សួស្តី 1"),
        SubtitleItem(id=2, start_ms=3500, end_ms=6000, src_text="World", tgt_text="ពិភពលោក 2"),
        SubtitleItem(id=3, start_ms=7000, end_ms=9000, src_text="Drama", tgt_text="រឿងភាគ 3")
    ]

    # Test time points
    def find_active_sub(ms):
        for s in subtitles:
            if s.start_ms <= ms < s.end_ms:
                return s
        return None

    assert find_active_sub(500) is None, "Failed at 500ms (should be None)"
    assert find_active_sub(1500).id == 1, "Failed at 1500ms (should be Sub 1)"
    assert find_active_sub(3200) is None, "Failed at 3200ms (gap, should be None)"
    assert find_active_sub(4000).id == 2, "Failed at 4000ms (should be Sub 2)"
    assert find_active_sub(8500).id == 3, "Failed at 8500ms (should be Sub 3)"
    print("[OK] Subtitle time range lookup passed.")

    print("\n=== 2. Testing ASS Style Formatting & Export Consistency ===")
    temp_ass_path = "temp/test_export_style.ass"
    os.makedirs("temp", exist_ok=True)

    style_cfg = {
        "font_name": "Khmer OS Battambang",
        "font_size": 28,
        "primary_color": "#FDCE2A",
        "outline_color": "#000000",
        "bg_color": "#1E1E2E",
        "outline_width": 3,
        "shadow_width": 2,
        "bold": True,
        "italic": False,
        "use_bg_box": True,
        "alignment": "Bottom Center",
        "sub_y_pct": 0.85
    }

    SubtitleParser.export_ass(subtitles, temp_ass_path, use_target=True, style_config=style_cfg)
    assert os.path.exists(temp_ass_path), "ASS file was not created"

    with open(temp_ass_path, "r", encoding="utf-8") as f:
        content = f.read()

    dialogue_lines = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogue_lines) == 3, f"Expected 3 dialogue lines, got {len(dialogue_lines)}"
    assert "PlayResY: 1080" in content, "PlayResY missing"
    assert "Khmer OS Battambang" in content, "Font name missing"
    print("[OK] ASS style formatting passed.")

    if os.path.exists(temp_ass_path):
        os.remove(temp_ass_path)

    print("\nALL SUBTITLE PREVIEW & EXPORT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_subtitle_preview_and_ass()
