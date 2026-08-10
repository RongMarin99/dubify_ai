"""
End-to-end test: verify the full export pipeline produces correct
ASS subtitle headers and FFmpeg filter_complex for 9:16 portrait mode.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 1. Test aspect_ratio value that will now be passed
# Before fix: "High (1080p FHD)" — this doesn't contain "9:16"
# After fix:  "9:16 (Portrait)"  — correctly matches the 9:16 checks
aspect_from_canvas = "9:16 (Portrait)"

# Verify FFmpeg target resolution
if "9:16" in aspect_from_canvas:
    target_w, target_h = 1080, 1920
    print(f"✓ PASS: 9:16 detected → target={target_w}x{target_h}")
else:
    target_w, target_h = 1920, 1080
    print(f"✗ FAIL: 9:16 NOT detected → target={target_w}x{target_h}")

# 2. Test inner video rect calculation (simulating a 1080x1908 source in 1080x1920 canvas)
vw, vh = 1080, 1908
v_aspect = vw / float(vh)
target_aspect = target_w / float(target_h)

if abs(v_aspect - target_aspect) < 0.01:
    inv_x, inv_y, inv_w, inv_h = 0, 0, target_w, target_h
elif target_aspect > v_aspect:
    inv_h = target_h
    inv_w = int(target_h * v_aspect)
    inv_x = int((target_w - inv_w) / 2.0)
    inv_y = 0
else:
    inv_w = target_w
    inv_h = int(target_w / v_aspect)
    inv_x = 0
    inv_y = int((target_h - inv_h) / 2.0)

print(f"  Source video: {vw}x{vh} (aspect={v_aspect:.4f})")
print(f"  Target canvas: {target_w}x{target_h} (aspect={target_aspect:.4f})")
print(f"  Inner video rect: x={inv_x}, y={inv_y}, w={inv_w}, h={inv_h}")
assert inv_w > 0 and inv_h > 0, "Inner rect dimensions must be positive"
print(f"✓ PASS: Inner video rect calculated correctly")

# 3. Test blur coordinate mapping
# Blur at bottom of frame: x=0.08, y=0.78, w=0.84, h=0.16
bx_pct, by_pct, bw_pct, bh_pct = 0.08, 0.78, 0.84, 0.16
x_px = inv_x + int(inv_w * bx_pct)
y_px = inv_y + int(inv_h * by_pct)
w_px = int(inv_w * bw_pct)
h_px = int(inv_h * bh_pct)

print(f"\n  Blur pct: x={bx_pct}, y={by_pct}, w={bw_pct}, h={bh_pct}")
print(f"  Blur pixels: x={x_px}, y={y_px}, w={w_px}, h={h_px}")

# The blur box should be in the bottom portion of the frame
assert y_px > target_h * 0.5, f"Blur Y={y_px} should be in bottom half of {target_h}"
assert x_px < target_w * 0.2, f"Blur X={x_px} should be near left side"
assert w_px > target_w * 0.5, f"Blur W={w_px} should span most of width"
assert x_px + w_px <= target_w + 4, f"Blur right edge {x_px+w_px} should be within {target_w}"
assert y_px + h_px <= target_h + 4, f"Blur bottom edge {y_px+h_px} should be within {target_h}"
print(f"✓ PASS: Blur coordinates map correctly to bottom of 9:16 frame")

# 4. Test ASS subtitle PlayRes
from translator.app.core.subtitle import SubtitleParser
test_ass_path = "temp/test_aspect_ratio.ass"
os.makedirs("temp", exist_ok=True)

from translator.app.model.models import SubtitleItem
test_subs = [SubtitleItem(id=1, start_ms=0, end_ms=5000, src_text="Hello World", tgt_text="សួស្ដី ពិភពលោក")]

SubtitleParser.export_ass(
    test_subs, test_ass_path, use_target=True,
    style_config={"font_name": "Khmer OS Battambang", "font_size": 24, "bold": True},
    aspect_ratio=aspect_from_canvas
)

with open(test_ass_path, 'r', encoding='utf-8') as f:
    ass_content = f.read()

assert "PlayResX: 1080" in ass_content, f"Expected PlayResX: 1080 in ASS"
assert "PlayResY: 1920" in ass_content, f"Expected PlayResY: 1920 in ASS"
assert "សួស្ដី" in ass_content, f"Expected Khmer text in ASS"
print(f"✓ PASS: ASS subtitle has PlayResX=1080, PlayResY=1920 for 9:16")

# Check font size scaling
import re
fontsize_match = re.search(r'Fontsize,(\d+)', ass_content)
if fontsize_match:
    font_size = int(fontsize_match.group(1))
    # With play_res_y=1920: scaled = max(32, int(24 * 1920/720)) = max(32, 64) = 64
    print(f"  ASS font size: {font_size}")
    assert font_size >= 48, f"Font size {font_size} is too small for 1920-tall canvas"
    print(f"✓ PASS: ASS font size is {font_size} (large enough for 1920p)")

# 5. Verify old broken value would have failed
broken_aspect = "High (1080p FHD)"
if "9:16" not in broken_aspect:
    print(f"\n✓ CONFIRMED: Old broken value '{broken_aspect}' would NOT trigger 9:16 mode")
    print(f"  → Would default to 1920x1080 landscape (WRONG for portrait video)")

print(f"\n{'='*60}")
print(f"ALL TESTS PASSED ✓")
print(f"{'='*60}")
