import os
import requests
from typing import List, Dict, Any

class LocalModelManager:
    """Detects and manages installed local AI models (Whisper, Faster Whisper, Ollama, Llama.cpp, VoxCPM2)."""
    
    @staticmethod
    def detect_all_models() -> List[Dict[str, Any]]:
        models = []
        
        # 1. Ollama Models (via HTTP API localhost:11434)
        ollama_models = LocalModelManager._detect_ollama_models()
        models.extend(ollama_models)
        
        # 2. Local Whisper / Faster-Whisper Models
        whisper_models = LocalModelManager._detect_whisper_models()
        models.extend(whisper_models)
        
        # 3. VoxCPM2 Local Model
        vox_model = LocalModelManager._detect_voxcpm2_model()
        models.extend(vox_model)
        
        # 4. Standard Supported List defaults (showing installation status)
        default_supported = [
            {"name": "Whisper Large v3", "version": "v3", "vram": "3.8 GB", "ram": "2.1 GB", "size": "3.1 GB", "status": "Not Installed", "type": "STT"},
            {"name": "Faster Whisper Medium", "version": "v2", "vram": "1.5 GB", "ram": "1.2 GB", "size": "1.4 GB", "status": "Not Installed", "type": "STT"},
            {"name": "DeepSeek R1 8B (Local)", "version": "8b-q4", "vram": "5.2 GB", "ram": "4.8 GB", "size": "4.9 GB", "status": "Not Installed", "type": "LLM"},
            {"name": "Qwen 2.5 7B (Local)", "version": "7b-instruct", "vram": "4.5 GB", "ram": "4.2 GB", "size": "4.4 GB", "status": "Not Installed", "type": "LLM"}
        ]
        
        existing_names = {m["name"] for m in models}
        for default_m in default_supported:
            if default_m["name"] not in existing_names:
                models.append(default_m)
                
        return models

    @staticmethod
    def _detect_ollama_models() -> List[Dict[str, Any]]:
        models = []
        try:
            res = requests.get("http://localhost:11434/api/tags", timeout=0.15)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("models", []):
                    name = item.get("name", "Ollama Model")
                    size_gb = round(item.get("size", 0) / (1024**3), 2)
                    models.append({
                        "name": f"Ollama: {name}",
                        "version": item.get("details", {}).get("parameter_size", "Local"),
                        "vram": f"~{max(1.0, round(size_gb * 1.1, 1))} GB",
                        "ram": f"~{size_gb} GB",
                        "size": f"{size_gb} GB",
                        "status": "Loaded",
                        "type": "LLM"
                    })
        except Exception:
            pass
        return models

    @staticmethod
    def _detect_whisper_models() -> List[Dict[str, Any]]:
        models = []
        # Check huggingface / whisper cache dir or C:\Users\RPC\.cache\huggingface\hub
        user_home = os.path.expanduser("~")
        hf_cache = os.path.join(user_home, ".cache", "huggingface", "hub")
        whisper_cache = os.path.join(user_home, ".cache", "whisper")
        
        found_base = False
        found_tiny = False
        
        if os.path.exists(whisper_cache):
            for f in os.listdir(whisper_cache):
                if "base" in f:
                    found_base = True
                if "tiny" in f:
                    found_tiny = True
                    
        models.append({
            "name": "Whisper Base (Local)",
            "version": "1.0",
            "vram": "0.5 GB",
            "ram": "0.4 GB",
            "size": "142 MB",
            "status": "Loaded" if found_base else "Not Installed",
            "type": "STT"
        })
        
        models.append({
            "name": "Whisper Tiny (Local)",
            "version": "1.0",
            "vram": "0.2 GB",
            "ram": "0.3 GB",
            "size": "75 MB",
            "status": "Loaded" if found_tiny else "Not Installed",
            "type": "STT"
        })
        
        return models

    @staticmethod
    def _detect_voxcpm2_model() -> List[Dict[str, Any]]:
        # Check if CosyVoice 2 / VoxCPM2 local service is running at http://localhost:50000
        status = "Not Installed"
        try:
            res = requests.get("http://localhost:50000/health", timeout=0.15)
            if res.status_code == 200:
                status = "Loaded"
        except Exception:
            pass
            
        return [{
            "name": "VoxCPM2 Khmer Localizer",
            "version": "v2.0",
            "vram": "2.8 GB",
            "ram": "3.5 GB",
            "size": "2.4 GB",
            "status": status,
            "type": "Localizer/STT"
        }]
