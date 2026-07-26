import os
from typing import List, Optional, Dict, Any
from .subtitle import SubtitleParser
from .ffmpeg import FFmpegManager
from ..model.models import SubtitleItem

class ExportManager:
    def __init__(self, ffmpeg_mgr: FFmpegManager):
        self.ffmpeg_mgr = ffmpeg_mgr

    def export_srt(self, subtitles: List[SubtitleItem], output_path: str, use_target: bool = True):
        SubtitleParser.export_srt(subtitles, output_path, use_target=use_target)

    def export_ass(
        self,
        subtitles: List[SubtitleItem],
        output_path: str,
        use_target: bool = True,
        style_config: Optional[Dict[str, Any]] = None
    ):
        SubtitleParser.export_ass(subtitles, output_path, use_target=use_target, style_config=style_config)

    def export_video(
        self,
        video_path: str,
        subtitles: List[SubtitleItem],
        output_video_path: str,
        style_config: Optional[Dict[str, Any]] = None,
        logo_config: Optional[Dict[str, Any]] = None,
        blur_config: Optional[Dict[str, Any]] = None,
        mute_original_audio: bool = True,
        audio_offset_ms: int = -2000,
        aspect_ratio: str = "Original",
        orig_audio_vol_pct: int = 20,
        temp_dir: str = "temp"
    ) -> bool:
        os.makedirs(temp_dir, exist_ok=True)

        # 1. Export Subtitle ASS
        temp_sub_path = os.path.join(temp_dir, "export_sub.ass")
        self.export_ass(subtitles, temp_sub_path, use_target=True, style_config=style_config)

        # 2. Merge generated TTS audio clips into full dubbed audio track (with lead time offset)
        temp_dubbed_audio = os.path.join(temp_dir, "merged_dubbed_track.wav")
        has_dubbed_track = self.ffmpeg_mgr.merge_tts_audio_tracks(subtitles, temp_dubbed_audio, audio_offset_ms=audio_offset_ms)

        # 3. Export Video with burned subtitles, logo, blur mask, aspect ratio, speech-gated ducking, and dubbed audio
        return self.ffmpeg_mgr.export_video_with_subtitles(
            video_path=video_path,
            subtitle_path=temp_sub_path,
            output_video_path=output_video_path,
            dubbed_audio_path=temp_dubbed_audio if has_dubbed_track else None,
            mute_original_audio=mute_original_audio,
            logo_config=logo_config,
            blur_config=blur_config,
            subtitles=subtitles,
            aspect_ratio=aspect_ratio,
            orig_audio_vol_pct=orig_audio_vol_pct
        )
