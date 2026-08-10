import sys
import random

def test_crop_math():
    sys.stdout.reconfigure(encoding='utf-8')
    target_w, target_h = 1080, 1920
    
    for i in range(1000):
        bx = random.uniform(-0.5, 1.5)
        by = random.uniform(-0.5, 1.5)
        bw = random.uniform(-0.5, 1.5)
        bh = random.uniform(-0.5, 1.5)
        
        # Clamped values
        bx_c = max(0.0, min(0.95, float(bx)))
        by_c = max(0.0, min(0.95, float(by)))
        bw_c = max(0.05, min(1.0, float(bw)))
        bh_c = max(0.05, min(1.0, float(bh)))

        x_px = int(target_w * bx_c)
        y_px = int(target_h * by_c)
        w_px = int(target_w * bw_c)
        h_px = int(target_h * bh_c)

        w_px = max(16, min(target_w - 4, w_px))
        h_px = max(16, min(target_h - 4, h_px))

        if x_px + w_px > target_w:
            x_px = max(0, target_w - w_px)
        if y_px + h_px > target_h:
            y_px = max(0, target_h - h_px)

        x_px = (x_px // 2) * 2
        y_px = (y_px // 2) * 2
        w_px = max(16, (w_px // 2) * 2)
        h_px = max(16, (h_px // 2) * 2)

        if x_px + w_px > target_w:
            w_px = ((target_w - x_px) // 2) * 2
        if y_px + h_px > target_h:
            h_px = ((target_h - y_px) // 2) * 2

        assert w_px >= 4, f"w_px failed: {w_px}"
        assert h_px >= 4, f"h_px failed: {h_px}"
        assert x_px >= 0, f"x_px failed: {x_px}"
        assert y_px >= 0, f"y_px failed: {y_px}"
        assert x_px + w_px <= target_w, f"x overflow: {x_px}+{w_px} > {target_w}"
        assert y_px + h_px <= target_h, f"y overflow: {y_px}+{h_px} > {target_h}"

    print("✓ 1,000 Crop Math Edge Cases Passed 100%!")

if __name__ == "__main__":
    test_crop_math()
