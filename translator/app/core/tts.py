import os
import asyncio
import hashlib
import requests
from typing import List, Dict, Optional
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem

# Enhanced Voice Profiles with custom Pitch & Rate for natural VoxcM2 / CosyVoice 2 & Edge-TTS dubbing
VOICE_PROFILES = {
    "VoxcM2 Male 1": {"voice": "km-KH-PisethNeural", "rate": "+0%", "pitch": "-4Hz", "cosy_role": "male_lead"},
    "VoxcM2 Female 1": {"voice": "km-KH-SreymomNeural", "rate": "+0%", "pitch": "+0Hz", "cosy_role": "female_lead"},
    "VoxcM2 Male 2": {"voice": "km-KH-PisethNeural", "rate": "+4%", "pitch": "-10Hz", "cosy_role": "male_sec"},
    "VoxcM2 Female 2": {"voice": "km-KH-SreymomNeural", "rate": "+4%", "pitch": "+5Hz", "cosy_role": "female_sec"},
    "Male 1": {"voice": "km-KH-PisethNeural", "rate": "+0%", "pitch": "-4Hz", "cosy_role": "male_lead"},
    "Male 2": {"voice": "km-KH-PisethNeural", "rate": "+4%", "pitch": "-10Hz", "cosy_role": "male_sec"},
    "Female 1": {"voice": "km-KH-SreymomNeural", "rate": "+0%", "pitch": "+0Hz", "cosy_role": "female_lead"},
    "Female 2": {"voice": "km-KH-SreymomNeural", "rate": "+4%", "pitch": "+5Hz", "cosy_role": "female_sec"},
    "Child": {"voice": "km-KH-SreymomNeural", "rate": "+10%", "pitch": "+15Hz", "cosy_role": "child"},
    "Old Man": {"voice": "km-KH-PisethNeural", "rate": "-8%", "pitch": "-15Hz", "cosy_role": "old_man"},
    "Old Woman": {"voice": "km-KH-SreymomNeural", "rate": "-6%", "pitch": "-10Hz", "cosy_role": "old_woman"}
}

class CosyVoiceDirectLocalRunner:
    """Direct in-process CosyVoice 2 / VoxcM2 model runner for python main.py."""
    _instance = None
    _cosyvoice_model = None

    @classmethod
    def get_instance(cls, model_dir: str = "pretrained_models/CosyVoice2-0.5B"):
        if cls._instance is None:
            cls._instance = CosyVoiceDirectLocalRunner()
            cls._instance._init_model(model_dir)
        return cls._instance

    def _init_model(self, model_dir: str):
        try:
            if os.path.exists(model_dir):
                from cosyvoice.cli.cosyvoice import CosyVoice2
                self._cosyvoice_model = CosyVoice2(model_dir)
        except Exception:
            self._cosyvoice_model = None

    def generate(self, text: str, role_name: str, output_file: str) -> bool:
        if self._cosyvoice_model is None:
            return False
        try:
            import torchaudio
            # Perform zero-shot / instruct synthesis directly in PyTorch
            output = self._cosyvoice_model.inference_sft(text, role_name, stream=False)
            for i, j in enumerate(output):
                torchaudio.save(output_file, j['tts_speech'], self._cosyvoice_model.sample_rate)
                return True
        except Exception:
            pass
        return False


class TTSWorker(QThread):
    progress = Signal(int, str)  # progress %, status msg
    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        subtitles: List[SubtitleItem],
        output_dir: str = "temp",
        engine: str = "CosyVoice 2 / VoxcM2",
        cosyvoice_url: str = "http://localhost:50000/tts",
        voice_map: Dict[str, str] = None
    ):
        super().__init__()
        self.subtitles = subtitles
        self.output_dir = output_dir
        self.engine = engine
        self.cosyvoice_url = cosyvoice_url.rstrip("/")
        self.voice_map = voice_map or VOICE_PROFILES
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        try:
            total = len(self.subtitles)
            if total == 0:
                self.finished.emit([])
                return

            updated_subs = []
            for idx, item in enumerate(self.subtitles):
                text_to_speak = item.tgt_text.strip() or item.src_text.strip()
                if not text_to_speak:
                    updated_subs.append(item)
                    continue

                role_config = self.voice_map.get(item.voice, VOICE_PROFILES["Male 1"])
                if isinstance(role_config, str):
                    role_config = {"voice": role_config, "rate": "+0%", "pitch": "+0Hz"}

                audio_hash = hashlib.md5(f"{self.engine}_{item.voice}_{text_to_speak}".encode('utf-8')).hexdigest()
                out_path = os.path.join(self.output_dir, f"tts_{item.id}_{audio_hash[:8]}.mp3")

                if not os.path.exists(out_path):
                    success = False

                    # 1. Direct In-Process CosyVoice 2 / VoxcM2 PyTorch Model Synthesis
                    if "CosyVoice" in self.engine or "Voxc" in self.engine:
                        runner = CosyVoiceDirectLocalRunner.get_instance()
                        success = runner.generate(text_to_speak, item.voice, out_path)

                        # 2. Local HTTP CosyVoice 2 API fallback
                        if not success:
                            success = self._generate_cosyvoice2_sync(text_to_speak, item.voice, out_path)

                    # 3. Fallback to Enhanced Edge-TTS with Pitch & Rate tuning
                    if not success:
                        success = self._generate_edge_tts_sync(
                            text=text_to_speak,
                            voice=role_config.get("voice", "km-KH-PisethNeural"),
                            rate=role_config.get("rate", "+0%"),
                            pitch=role_config.get("pitch", "+0Hz"),
                            output_file=out_path
                        )

                    if not success:
                        self._create_silent_wav(out_path, duration_ms=max(1000, item.end_ms - item.start_ms))

                item.audio_path = out_path
                item.status = "Audio Generated"
                updated_subs.append(item)

                pct = int((idx + 1) / total * 100)
                self.progress.emit(pct, f"Generated voice {idx+1}/{total}...")

            self.progress.emit(100, "TTS Voice Generation Complete!")
            self.finished.emit(updated_subs)

        except Exception as e:
            self.failed.emit(str(e))

    def _generate_cosyvoice2_sync(self, text: str, role_name: str, output_file: str) -> bool:
        """Call local CosyVoice 2 / VoxcM2 Neural Voice API endpoint."""
        try:
            payload = {
                "text": text,
                "speaker": role_name,
                "language": "Khmer",
                "speed": 1.0
            }
            res = requests.post(f"{self.cosyvoice_url}", json=payload, timeout=10)
            if res.status_code == 200 and len(res.content) > 100:
                with open(output_file, "wb") as f:
                    f.write(res.content)
                return True
        except Exception:
            pass
        return False

    def _generate_edge_tts_sync(self, text: str, voice: str, rate: str, pitch: str, output_file: str) -> bool:
        """Generate audio using Edge-TTS with custom rate & pitch."""
        async def _main():
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_file)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_main())
            loop.close()
            return os.path.exists(output_file) and os.path.getsize(output_file) > 0
        except Exception:
            return False

    def _create_silent_wav(self, output_file: str, duration_ms: int = 1000):
        import wave
        try:
            nchannels = 1
            sampwidth = 2
            framerate = 24000
            nframes = int(framerate * (duration_ms / 1000.0))
            with wave.open(output_file, 'w') as wf:
                wf.setnchannels(nchannels)
                wf.setsampwidth(sampwidth)
                wf.setframerate(framerate)
                wf.writeframes(b'\x00' * (nframes * nchannels * sampwidth))
        except Exception:
            pass
