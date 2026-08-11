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
        style_config: Optional[Dict[str, Any]] = None,
        aspect_ratio: str = "Original"
    ):
        SubtitleParser.export_ass(subtitles, output_path, use_target=use_target, style_config=style_config, aspect_ratio=aspect_ratio)

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
        mute_all_audio: bool = False,
        burn_subtitles: bool = True,
        temp_dir: str = "temp"
    ) -> bool:
        os.makedirs(temp_dir, exist_ok=True)

        concat_path = None
        if burn_subtitles:
            # 1. Determine Target Dimensions for Subtitle PNG rendering
            # Match FFmpeg target dimensions logic based on aspect ratio mode
            if "9:16" in aspect_ratio:
                target_w, target_h = 1080, 1920
            elif "16:9" in aspect_ratio:
                target_w, target_h = 1920, 1080
            elif "1:1" in aspect_ratio:
                target_w, target_h = 1080, 1080
            elif "4:5" in aspect_ratio:
                target_w, target_h = 1080, 1350
            else:
                target_w, target_h = self.ffmpeg_mgr.get_video_dimensions(video_path)

            # 2. Render pixel-perfect transparent PNG subtitles sequence via Qt QPainter
            # to guarantee 100% synchronization with the UI preview layout.
            from .subtitle_renderer import SubtitleRenderer
            renderer = SubtitleRenderer(style_config, aspect_ratio, target_w, target_h)
            concat_path = renderer.generate_concat_video(subtitles, os.path.join(temp_dir, "subs_frames"))

        # 3. Merge generated TTS audio clips into full dubbed audio track
        temp_dubbed_audio = os.path.join(temp_dir, "merged_dubbed_track.wav")
        has_dubbed_track = self.ffmpeg_mgr.merge_tts_audio_tracks(subtitles, temp_dubbed_audio, audio_offset_ms=audio_offset_ms)

        # 4. Export Video with burned subtitles, logo, blur mask, aspect ratio, speech-gated ducking, and dubbed audio
        return self.ffmpeg_mgr.export_video_with_subtitles(
            video_path=video_path,
            subtitle_concat_path=concat_path,
            output_video_path=output_video_path,
            dubbed_audio_path=temp_dubbed_audio if has_dubbed_track else None,
            mute_original_audio=mute_original_audio,
            logo_config=logo_config,
            blur_config=blur_config,
            subtitles=subtitles,
            aspect_ratio=aspect_ratio,
            orig_audio_vol_pct=orig_audio_vol_pct,
            mute_all_audio=mute_all_audio
        )
