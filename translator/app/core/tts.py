import os
import asyncio
import hashlib
import subprocess
import requests
from typing import List, Dict, Optional
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem


def has_nvidia_gpu() -> bool:
    """Cheap check for an NVIDIA/CUDA-capable GPU via nvidia-smi, without needing
    torch installed. VoxCPM2 requires CUDA >=12.0 in practice — on machines with
    only integrated graphics (Intel/AMD APU), it can never run regardless of which
    Python packages are installed, so we should say that plainly instead of letting
    a raw ModuleNotFoundError/CUDA error look like something's broken."""
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        return result.returncode == 0
    except Exception:
        return False

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

# Voice-design descriptors — VoxCPM2 has no pitch/rate knobs like Edge-TTS; instead
# you prefix the text with a natural-language "(voice description)" and the diffusion
# model synthesizes a matching voice. This keeps our existing voice-profile picker
# working the same way, just mapped to descriptors instead of Hz/percent values.
VOXCPM2_VOICE_DESIGN = {
    "male_lead": "(A calm adult male voice, natural warm tone)",
    "male_sec": "(An energetic adult male voice, slightly faster pace)",
    "female_lead": "(A calm adult female voice, natural warm tone)",
    "female_sec": "(An energetic adult female voice, slightly faster pace)",
    "child": "(A young child's voice, high-pitched and playful)",
    "old_man": "(An elderly male voice, slow and gravelly)",
    "old_woman": "(An elderly female voice, slow and soft)",
}


class VoxCPM2KhmerRunner:
    """Direct in-process sumnim/VoxCPM2-Khmer synthesis — realistic diffusion-based
    Khmer TTS. Requires the `voxcpm` package + a CUDA GPU (the official API has no
    practical CPU path); falls through to Edge-TTS automatically if unavailable."""
    _instance = None
    _model = None
    _load_failed = False
    _failure_reason = ""

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = VoxCPM2KhmerRunner()
            cls._instance._init_model()
        return cls._instance

    def _init_model(self):
        if not has_nvidia_gpu():
            self._model = None
            self._load_failed = True
            self._failure_reason = "No NVIDIA/CUDA GPU detected on this machine — VoxCPM2 requires one."
            return
        try:
            from voxcpm import VoxCPM
            self._model = VoxCPM.from_pretrained("sumnim/VoxCPM2-Khmer")
        except Exception as e:
            self._model = None
            self._load_failed = True
            self._failure_reason = str(e)

    def generate(self, text: str, role_config: dict, output_file: str) -> bool:
        if self._model is None:
            return False
        try:
            import soundfile as sf
            descriptor = VOXCPM2_VOICE_DESIGN.get(role_config.get("cosy_role", ""), "")
            wav = self._model.generate(
                text=f"{descriptor}{text}" if descriptor else text,
                cfg_value=2.0,
                inference_timesteps=6,
            )
            sf.write(output_file, wav, self._model.tts_model.sample_rate)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return True
            self._failure_reason = "generate() ran but produced no/empty audio file"
            return False
        except Exception as e:
            self._failure_reason = str(e)
            return False


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
    warnings = Signal(list)  # human-readable messages for lines that fell back to silence or produced no audio at all
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
        self._last_error = ""
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        try:
            total = len(self.subtitles)
            if total == 0:
                self.finished.emit([])
                return

            updated_subs = []
            line_warnings = []
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

                # A 0-byte leftover from a previous interrupted run would otherwise look
                # "already generated" and get skipped forever — treat it as missing.
                if os.path.exists(out_path) and os.path.getsize(out_path) == 0:
                    os.remove(out_path)

                if not os.path.exists(out_path):
                    success = False
                    fail_reasons = []

                    # 1. sumnim/VoxCPM2-Khmer — real diffusion TTS, most realistic Khmer
                    if "VoxCPM2" in self.engine:
                        runner = VoxCPM2KhmerRunner.get_instance()
                        success = runner.generate(text_to_speak, role_config, out_path)
                        if not success:
                            reason = runner._failure_reason or "No CUDA GPU / Model missing"
                            fail_reasons.append(f"VoxCPM2: {reason}")
                            self.progress.emit(
                                int((idx) / total * 100),
                                f"VoxCPM2 unavailable ({reason[:35]}) — Auto falling back to Edge-TTS..."
                            )

                    # 2. Direct In-Process CosyVoice 2 PyTorch Model Synthesis
                    if not success and ("CosyVoice" in self.engine or "Voxc" in self.engine):
                        runner = CosyVoiceDirectLocalRunner.get_instance()
                        success = runner.generate(text_to_speak, item.voice, out_path)
                        if not success:
                            fail_reasons.append("CosyVoice2 local model unavailable")

                            # 2b. Local HTTP CosyVoice 2 API fallback
                            success = self._generate_cosyvoice2_sync(text_to_speak, item.voice, out_path)
                            if not success:
                                fail_reasons.append(f"CosyVoice2 HTTP API: {self._last_error or 'unreachable'}")

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
                            fail_reasons.append(f"Edge-TTS: {self._last_error or 'request failed (check internet connection)'}")

                    if not success:
                        self._create_silent_wav(out_path, duration_ms=max(1000, item.end_ms - item.start_ms))
                        if os.path.exists(out_path):
                            preview = text_to_speak[:40] + ("..." if len(text_to_speak) > 40 else "")
                            line_warnings.append(
                                f"Line {item.id} \"{preview}\": all TTS engines failed ({'; '.join(fail_reasons) or 'unknown error'}) — using silence instead."
                            )
                        else:
                            line_warnings.append(
                                f"Line {item.id}: TTS AND silent-audio fallback both failed ({self._last_error or 'unknown error'}) — this line will have NO audio in the export."
                            )

                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    item.audio_path = out_path
                    item.status = "Audio Generated"
                else:
                    item.audio_path = ""
                    item.status = "Audio Failed"
                updated_subs.append(item)

                pct = int((idx + 1) / total * 100)
                self.progress.emit(pct, f"Generated voice {idx+1}/{total}...")

            self.progress.emit(100, "TTS Voice Generation Complete!")
            if line_warnings:
                self.warnings.emit(line_warnings)
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
            self._last_error = f"HTTP {res.status_code}"
        except Exception as e:
            self._last_error = str(e)
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
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return True
            self._last_error = "produced no/empty audio file"
            return False
        except Exception as e:
            self._last_error = str(e)
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
        except Exception as e:
            self._last_error = f"silent WAV write failed: {e}"
