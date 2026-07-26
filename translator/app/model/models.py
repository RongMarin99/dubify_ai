from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class SubtitleItem:
    id: int
    start_ms: int
    end_ms: int
    src_text: str = ""
    tgt_text: str = ""
    voice: str = "Male 1"
    status: str = "Pending"  # Pending, Translated, Audio Generated, Error
    audio_path: Optional[str] = None
    character_name: Optional[str] = None
    confidence: float = 1.0

    @property
    def start_timecode(self) -> str:
        return self.ms_to_timecode(self.start_ms)

    @property
    def end_timecode(self) -> str:
        return self.ms_to_timecode(self.end_ms)

    @staticmethod
    def ms_to_timecode(ms: int) -> str:
        hours = ms // (3600 * 1000)
        ms %= (3600 * 1000)
        minutes = ms // (60 * 1000)
        ms %= (60 * 1000)
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    @staticmethod
    def timecode_to_ms(tc: str) -> int:
        try:
            tc = tc.replace(',', '.')
            parts = tc.split(':')
            if len(parts) == 3:
                h = int(parts[0])
                m = int(parts[1])
                sec_parts = parts[2].split('.')
                s = int(sec_parts[0])
                ms = int(sec_parts[1]) if len(sec_parts) > 1 else 0
                if len(sec_parts) > 1 and len(sec_parts[1]) < 3:
                    ms *= 10 ** (3 - len(sec_parts[1]))
                return h * 3600000 + m * 60000 + s * 1000 + ms
            elif len(parts) == 2:
                m = int(parts[0])
                sec_parts = parts[1].split('.')
                s = int(sec_parts[0])
                ms = int(sec_parts[1]) if len(sec_parts) > 1 else 0
                return m * 60000 + s * 1000 + ms
        except Exception:
            pass
        return 0

@dataclass
class VoiceProfile:
    id: int
    name: str
    gender: str  # Male, Female, Child, Old Man, Old Woman
    voice_id: str  # e.g., "km-KH-PisethNeural" or "km-KH-SreymomNeural"
    engine: str = "Edge TTS"
    pitch: float = 1.0
    speed: float = 1.0

@dataclass
class BlurObject:
    id: int = 1
    x_pct: float = 0.08
    y_pct: float = 0.80
    w_pct: float = 0.84
    h_pct: float = 0.12
    blur_strength: int = 50
    opacity: float = 0.90
    border_radius: int = 4
    feather: int = 5
    start_time_ms: int = 0
    end_time_ms: int = 3600000
    enabled: bool = True

@dataclass
class SubtitleOverlayObject:
    id: int = 1
    text: str = ""
    x_pct: float = 0.50
    y_pct: float = 0.85
    w_pct: float = 0.80
    h_pct: float = 0.10
    font_family: str = "Khmer OS Battambang"
    font_size: int = 24
    bold: bool = True
    italic: bool = False
    outline_color: str = "#000000"
    primary_color: str = "#FFFFFF"
    background_color: str = "#000000"
    opacity: float = 1.0
    alignment: str = "Bottom Center"
    start_time_ms: int = 0
    end_time_ms: int = 3600000

@dataclass
class ProjectModel:
    id: Optional[int] = None
    name: str = "Untitled Project"
    video_path: str = ""
    audio_path: str = ""
    source_lang: str = "Chinese"
    target_lang: str = "Khmer"
    bgm_path: str = ""
    created_at: str = ""
