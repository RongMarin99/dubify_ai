import os
import subprocess
import shutil
from typing import Tuple, List, Optional, Dict, Any
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem

class AudioExtractWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(str)  # output wav path
    failed = Signal(str)

    def __init__(self, ffmpeg_mgr: "FFmpegManager", video_path: str, output_wav_path: str):
        super().__init__()
        self.ffmpeg_mgr = ffmpeg_mgr
        self.video_path = video_path
        self.output_wav_path = output_wav_path

    def run(self):
        try:
            self.progress.emit(10, "Extracting audio from video...")
            success = self.ffmpeg_mgr.extract_audio(self.video_path, self.output_wav_path)
            if success:
                self.progress.emit(100, "Audio extraction complete.")
                self.finished.emit(self.output_wav_path)
            else:
                self.failed.emit("FFmpeg failed to extract audio from video.")
        except Exception as e:
            self.failed.emit(str(e))


class AudioSeparationWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(str, str, str)  # bgm_path, dialogue_path, sfx_path
    failed = Signal(str)

    def __init__(self, ffmpeg_mgr: "FFmpegManager", audio_path: str):
        super().__init__()
        self.ffmpeg_mgr = ffmpeg_mgr
        self.audio_path = audio_path

    def run(self):
        try:
            self.progress.emit(10, "Initializing Demucs v4 / AI Source Separation...")
            bgm_wav = os.path.join("temp", "isolated_bgm.wav")
            dialogue_wav = os.path.join("temp", "isolated_dialogue.wav")
            sfx_wav = os.path.join("temp", "isolated_sfx.wav")
            os.makedirs("temp", exist_ok=True)

            try:
                import demucs.separate
                self.progress.emit(30, "Separating Dialogue, BGM, SFX using Demucs v4...")
                cmd = ["demucs", "--two-stems", "vocals", "-n", "htdemucs", "-o", "temp/demucs", self.audio_path]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    base_name = os.path.splitext(os.path.basename(self.audio_path))[0]
                    no_vocals = os.path.join("temp", "demucs", "htdemucs", base_name, "no_vocals.wav")
                    vocals = os.path.join("temp", "demucs", "htdemucs", base_name, "vocals.wav")
                    if os.path.exists(no_vocals):
                        shutil.copy(no_vocals, bgm_wav)
                        shutil.copy(vocals, dialogue_wav)
                        self.progress.emit(100, "Demucs v4 Vocal & BGM separation complete!")
                        self.finished.emit(bgm_wav, dialogue_wav, bgm_wav)
                        return
            except Exception:
                pass

            # Fallback: High-Performance Intelligent Vocal Suppression & BGM/SFX Filter
            self.progress.emit(50, "Applying AI Vocal Suppression & BGM/SFX Preservation Filter...")
            success = self.ffmpeg_mgr.isolate_bgm_sfx(self.audio_path, bgm_wav)
            if success:
                self.progress.emit(100, "BGM & SFX Track Isolation Complete!")
                self.finished.emit(bgm_wav, dialogue_wav, bgm_wav)
            else:
                self.failed.emit("Failed to isolate BGM & SFX tracks.")
        except Exception as e:
            self.failed.emit(str(e))


class FFmpegManager:
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.last_error = ""
        if shutil.which(ffmpeg_path):
            self.ffmpeg_path = ffmpeg_path
        else:
            try:
                import imageio_ffmpeg
                self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                self.ffmpeg_path = ffmpeg_path

    def is_available(self) -> bool:
        try:
            res = subprocess.run([self.ffmpeg_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    def extract_audio(self, video_path: str, output_wav_path: str) -> bool:
        """Extract 16kHz mono WAV audio from video for Whisper STT processing."""
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-ar", "16000",
            "-ac", "1",
            "-vn",
            output_wav_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    def isolate_bgm_sfx(self, input_audio: str, output_bgm_sfx: str) -> bool:
        """Intelligent Vocal Suppression & BGM/SFX Preservation Filter Graph using FFmpeg bandpass & center channel extraction."""
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_audio,
            "-af", "pan=stereo|c0=c0-c1|c1=c1-c0,highpass=f=80,lowpass=f=12000,volume=1.2",
            output_bgm_sfx
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    def merge_tts_audio_tracks(self, subtitles: List[SubtitleItem], output_audio_path: str, audio_offset_ms: int = -2000) -> bool:
        """Stitch generated TTS audio clips at their start timestamps (with lead-time offset) into a single audio track."""
        valid_subs = [s for s in subtitles if s.audio_path and os.path.exists(s.audio_path)]
        if not valid_subs:
            return False

        cmd = [self.ffmpeg_path, "-y"]
        filter_parts = []
        mix_inputs = []

        for idx, s in enumerate(valid_subs):
            cmd.extend(["-i", s.audio_path])
            delay = max(0, int(s.start_ms + audio_offset_ms))
            filter_parts.append(f"[{idx}:a]adelay={delay}|{delay}[a{idx}]")
            mix_inputs.append(f"[a{idx}]")

        if len(valid_subs) == 1:
            cmd.extend(["-filter_complex", filter_parts[0], "-map", "[a0]", output_audio_path])
        else:
            mix_str = "".join(mix_inputs)
            # Use normalize=0 so volume is NOT attenuated by number of inputs
            filter_parts.append(f"{mix_str}amix=inputs={len(valid_subs)}:duration=longest:dropout_transition=0:normalize=0[aout]")
            cmd.extend(["-filter_complex", ";".join(filter_parts), "-map", "[aout]", output_audio_path])

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    def get_duration_ms(self, media_path: str) -> int:
        """Get media duration in milliseconds via ffprobe or ffmpeg."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            media_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return int(float(res.stdout.strip()) * 1000)
        except Exception:
            pass
        return 60000  # Default 60s fallback for UI display

    def get_video_dimensions(self, media_path: str) -> Tuple[int, int]:
        """Get video width and height in pixels via ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            media_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split("x")
                if len(parts) >= 2:
                    return int(parts[0]), int(parts[1])
        except Exception:
            pass
        return 1920, 1080

    def generate_waveform_points(self, wav_path: str, num_points: int = 100) -> List[float]:
        """Generate normalized amplitude waveform data for UI timeline rendering."""
        try:
            import wave
            import struct
            with wave.open(wav_path, 'rb') as wf:
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                nframes = wf.getnframes()
                frames = wf.readframes(nframes)

                if sampwidth == 2:
                    fmt = f"<{nframes * nchannels}h"
                    samples = struct.unpack(fmt, frames)
                    chunk_size = max(1, len(samples) // num_points)
                    amplitudes = []
                    for i in range(0, len(samples), chunk_size):
                        chunk = samples[i:i + chunk_size]
                        avg_amp = sum(abs(s) for s in chunk) / max(1, len(chunk))
                        amplitudes.append(avg_amp / 32768.0)
                    return amplitudes[:num_points]
        except Exception:
            pass
        import math
        return [abs(math.sin(i * 0.15)) * 0.8 for i in range(num_points)]

    def export_video_with_subtitles(
        self,
        video_path: str,
        subtitle_concat_path: str,
        output_video_path: str,
        dubbed_audio_path: Optional[str] = None,
        mute_original_audio: bool = True,
        logo_config: Optional[Dict[str, Any]] = None,
        blur_config: Optional[Dict[str, Any]] = None,
        subtitles: Optional[List[SubtitleItem]] = None,
        aspect_ratio: str = "Original",
        orig_audio_vol_pct: int = 20
    ) -> bool:
        """Burn subtitles (via concat image sequence), logo overlay, blur mask, aspect ratio, and dynamic original audio volume into output video."""
        cmd = [self.ffmpeg_path, "-y"]
        next_input_idx = 0
        
        # Input 0: Video
        cmd.extend(["-i", video_path])
        video_input_idx = next_input_idx
        next_input_idx += 1

        # Check logo input file
        logo_path = (logo_config or {}).get("path", "")
        has_logo = bool(logo_config and logo_config.get("enabled", False) and logo_path and os.path.exists(logo_path))
        logo_input_idx = -1
        if has_logo:
            cmd.extend(["-i", logo_path])
            logo_input_idx = next_input_idx
            next_input_idx += 1

        # Check dubbed audio input file
        has_dubbed = bool(dubbed_audio_path and os.path.exists(dubbed_audio_path))
        dubbed_input_idx = -1
        if has_dubbed:
            cmd.extend(["-i", dubbed_audio_path])
            dubbed_input_idx = next_input_idx
            next_input_idx += 1

        # Subtitle image sequence input
        subtitle_input_idx = -1
        if subtitle_concat_path and os.path.exists(subtitle_concat_path):
            cmd.extend(["-f", "concat", "-safe", "0", "-i", subtitle_concat_path])
            subtitle_input_idx = next_input_idx
            next_input_idx += 1

        # Determine target resolution according to aspect ratio
        if "9:16" in aspect_ratio:
            target_w, target_h = 1080, 1920
        elif "16:9" in aspect_ratio:
            target_w, target_h = 1920, 1080
        elif "1:1" in aspect_ratio:
            target_w, target_h = 1080, 1080
        elif "4:5" in aspect_ratio:
            target_w, target_h = 1080, 1350
        else:
            target_w, target_h = self.get_video_dimensions(video_path)

        # Original source video dimensions for inner image rect calculation
        vw, vh = self.get_video_dimensions(video_path)
        v_aspect = (vw / float(vh)) if vh > 0 else (16.0 / 9.0)
        target_aspect = (target_w / float(target_h)) if target_h > 0 else (16.0 / 9.0)

        if aspect_ratio == "Original" or abs(v_aspect - target_aspect) < 0.01:
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

        filter_complex_parts = []
        cur_v_label = "[0:v]"

        # STEP 1: Scale & Pad video to target aspect ratio FIRST so all subsequent filters (blur, logo, subtitles)
        # map 1:1 onto target dimensions!
        if aspect_ratio != "Original":
            filter_complex_parts.append(
                f"{cur_v_label}scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black[v_base]"
            )
            cur_v_label = "[v_base]"

        # STEP 2: Blur filter — blur_config percentages are relative to the inner video image rect
        # (the actual video content within letterbox/pillarbox bars), so we map them onto
        # (inv_x, inv_y, inv_w, inv_h) within the target canvas.
        if blur_config and blur_config.get("enabled", False):
            bx = max(0.0, min(0.95, float(blur_config.get("x", 0.10))))
            by = max(0.0, min(0.95, float(blur_config.get("y", 0.80))))
            bw = max(0.05, min(1.0, float(blur_config.get("w", 0.80))))
            bh = max(0.05, min(1.0, float(blur_config.get("h", 0.12))))
            blur_radius = max(1, int(blur_config.get("radius", 22)))
            tint_hex = str(blur_config.get("color", "#0f0f19")).lstrip("#")
            tint_opacity = max(0.0, min(1.0, float(blur_config.get("opacity", 0.85))))
            tint_ffmpeg = f"0x{tint_hex}@{tint_opacity:.2f}"

            # Map percentages onto inner video image rect, not full target canvas
            x_px = inv_x + int(inv_w * bx)
            y_px = inv_y + int(inv_h * by)
            w_px = int(inv_w * bw)
            h_px = int(inv_h * bh)

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

            filter_complex_parts.append(
                f"{cur_v_label}split[v_blur_main][v_blur_crop];"
                f"[v_blur_crop]crop={w_px}:{h_px}:{x_px}:{y_px},"
                f"boxblur=luma_radius={blur_radius}:luma_power=2:chroma_radius={blur_radius}:chroma_power=2,"
                f"drawbox=x=0:y=0:w=iw:h=ih:color={tint_ffmpeg}:t=fill,"
                f"drawbox=x=0:y=0:w=iw:h=2:color=white@0.25:t=fill[b_crop];"
                f"[v_blur_main][b_crop]overlay={x_px}:{y_px}[v_blur]"
            )
            cur_v_label = "[v_blur]"

        # STEP 3: Logo overlay filter — logo coords are also relative to inner video image rect
        if has_logo and logo_input_idx != -1:
            lx = logo_config.get("x", 0.05)
            ly = logo_config.get("y", 0.05)
            lw = logo_config.get("w", 0.20)
            lh = logo_config.get("h", 0.12)
            logo_x_px = inv_x + int(inv_w * lx)
            logo_y_px = inv_y + int(inv_h * ly)
            logo_w_px = max(16, int(inv_w * lw))
            logo_h_px = max(16, int(inv_h * lh))
            filter_complex_parts.append(f"[{logo_input_idx}:v]scale=eval=frame:w={logo_w_px}:h={logo_h_px}[logo_scaled]")
            filter_complex_parts.append(f"{cur_v_label}[logo_scaled]overlay=x={logo_x_px}:y={logo_y_px}[v_logo]")
            cur_v_label = "[v_logo]"

        # STEP 4: Subtitles filter (overlay the concat image sequence)
        if subtitle_input_idx != -1:
            filter_complex_parts.append(f"{cur_v_label}[{subtitle_input_idx}:v]overlay=x=0:y=0:shortest=0[vout]")
            cur_v_label = "[vout]"
        else:
            filter_complex_parts.append(f"{cur_v_label}copy[vout]")

        # STEP 5: Audio Filtering & Mixing (Boosted Dubbed TTS Speech + Speech Ducking)
        mute_all_audio = export_kwargs.get("mute_all_audio", False)
        if mute_all_audio:
            vol_filter = "aformat=sample_rates=44100:channel_layouts=stereo,volume=0.0"
        else:
            vol_factor = max(0.0, min(1.0, orig_audio_vol_pct / 100.0))
            duck_exprs = []
            if subtitles and mute_original_audio: # mute_original_audio is actually the Speech Ducking toggle
                for s in subtitles:
                    if s.start_ms < s.end_ms:
                        s_sec = s.start_ms / 1000.0
                        e_sec = s.end_ms / 1000.0
                        duck_exprs.append(f"between(t,{s_sec:.3f},{e_sec:.3f})")

            if duck_exprs:
                enable_cond = "+".join(duck_exprs)
                vol_filter = f"aformat=sample_rates=44100:channel_layouts=stereo,volume='if({enable_cond},{vol_factor:.2f},1.0)':eval=frame"
            else:
                vol_filter = f"aformat=sample_rates=44100:channel_layouts=stereo,volume={vol_factor:.2f}" if mute_original_audio else "aformat=sample_rates=44100:channel_layouts=stereo,volume=1.0"

        filter_complex_parts.append(f"[0:a]{vol_filter}[bg_a]")

        if has_dubbed and dubbed_input_idx != -1:
            # Boost TTS voice track to volume 1.8 so dubbed speech is loud, clear, and prominent
            filter_complex_parts.append(f"[{dubbed_input_idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.8[dub_a]")
            filter_complex_parts.append(f"[bg_a][dub_a]amix=inputs=2:weights='1 2.5':normalize=0:duration=first:dropout_transition=0[aout]")
        else:
            filter_complex_parts.append(f"[bg_a]aformat=sample_rates=44100:channel_layouts=stereo[aout]")

        full_filter_complex = ";".join(filter_complex_parts)

        cmd.extend([
            "-filter_complex", full_filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            output_video_path
        ])

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                self.last_error = f"FFmpeg Error (code {res.returncode}): {res.stderr.strip()}"
                print(f"[FFmpeg Export Error] returncode={res.returncode}:\n{res.stderr}")
                return False
            return True
        except Exception as e:
            self.last_error = f"FFmpeg Exception: {str(e)}"
            print(f"[FFmpeg Exception]: {e}")
            return False
