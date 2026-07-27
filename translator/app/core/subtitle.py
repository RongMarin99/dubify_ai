import re
from typing import List, Optional, Dict, Any
from ..model.models import SubtitleItem

def hex_to_ass_color(hex_str: str) -> str:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        r, g, b = hex_str[0:2], hex_str[2:4], hex_str[4:6]
        return f"&H00{b}{g}{r}".upper()
    return "&H00FFFFFF"

class SubtitleParser:
    @staticmethod
    def parse_srt(file_path: str) -> List[SubtitleItem]:
        subtitles = []
        with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read().strip()

        blocks = re.split(r'\n\s*\n', content)
        sub_id = 1
        for block in blocks:
            lines = [line.strip() for line in block.split('\n') if line.strip()]
            if len(lines) >= 2:
                time_line_idx = 1 if lines[0].isdigit() else 0
                if '-->' in lines[time_line_idx]:
                    times = lines[time_line_idx].split('-->')
                    start_ms = SubtitleItem.timecode_to_ms(times[0].strip())
                    end_ms = SubtitleItem.timecode_to_ms(times[1].strip())
                    text = " ".join(lines[time_line_idx + 1:])
                    subtitles.append(SubtitleItem(
                        id=sub_id,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        src_text=text,
                        tgt_text="",
                        status="Pending"
                    ))
                    sub_id += 1
        return subtitles

    @staticmethod
    def export_srt(subtitles: List[SubtitleItem], output_path: str, use_target: bool = True):
        with open(output_path, 'w', encoding='utf-8') as f:
            for idx, item in enumerate(subtitles, 1):
                start_tc = SubtitleItem.ms_to_timecode(item.start_ms).replace('.', ',')
                end_tc = SubtitleItem.ms_to_timecode(item.end_ms).replace('.', ',')
                text = (item.tgt_text if use_target and item.tgt_text else item.src_text) or ""
                f.write(f"{idx}\n{start_tc} --> {end_tc}\n{text}\n\n")

    @staticmethod
    def export_ass(
        subtitles: List[SubtitleItem],
        output_path: str,
        use_target: bool = True,
        style_config: Optional[Dict[str, Any]] = None
    ):
        cfg = style_config or {}
        font_name = cfg.get("font_name", "Khmer OS Battambang")
        font_size = int(cfg.get("font_size", 24))
        primary_hex = cfg.get("primary_color", "#FFFFFF")
        outline_hex = cfg.get("outline_color", "#000000")
        bg_hex = cfg.get("bg_color", "#000000")
        outline_w = int(cfg.get("outline_width", 2))
        shadow_w = int(cfg.get("shadow_width", 1))
        bold_val = 1 if cfg.get("bold", True) else 0
        italic_val = 1 if cfg.get("italic", False) else 0
        use_bg_box = cfg.get("use_bg_box", False)

        align_map = {
            "Bottom Center": 2, "Bottom Left": 1, "Bottom Right": 3,
            "Top Center": 8, "Middle": 5
        }
        align_val = align_map.get(cfg.get("alignment", "Bottom Center"), 2)

        # Compute vertical margin from sub_y_pct (assuming 1080p ASS PlayResY)
        sub_y_pct = float(cfg.get("sub_y_pct", 0.85))
        margin_v = max(10, min(1000, int((1.0 - sub_y_pct) * 1080)))

        pri_ass = hex_to_ass_color(primary_hex)
        out_ass = hex_to_ass_color(outline_hex)
        back_ass = hex_to_ass_color(bg_hex)

        border_style = 3 if use_bg_box else 1  # 3 = opaque box, 1 = outline + shadow

        header = f"""[Script Info]
Title: Dubify Studio Professional Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{pri_ass},&H000000FF,{out_ass},{back_ass},{bold_val},{italic_val},0,0,100,100,0,0,{border_style},{outline_w},{shadow_w},{align_val},20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(header)
            for item in subtitles:
                start_tc = SubtitleItem.ms_to_timecode(item.start_ms)[:10]
                end_tc = SubtitleItem.ms_to_timecode(item.end_ms)[:10]
                text = (item.tgt_text if use_target and item.tgt_text else item.src_text) or ""
                # Replace newlines with ASS \N for 2-line auto wrapping
                text_ass = text.replace("\n", "\\N")
                f.write(f"Dialogue: 0,{start_tc},{end_tc},Default,,0,0,0,,{text_ass}\n")
