import requests
from typing import List, Optional
from .base import BaseAIProvider

class OllamaProvider(BaseAIProvider):
    def __init__(self, host: str = "http://localhost:11434", model_name: str = "qwen2.5:7b"):
        self.host = host.rstrip("/")
        self.model_name = model_name

    def translate(
        self,
        text: str,
        source_lang: str = "Chinese",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        context_prev: str = "",
        context_next: str = "",
        temperature: float = 0.3
    ) -> str:
        if not text.strip():
            return ""

        system_prompt = prompt_template or f"You are a subtitle translator. Translate from {source_lang} to natural spoken {target_lang}. Return ONLY the target line translation."
        prompt = f"{system_prompt}\n"
        if context_prev or context_next:
            prompt += f"Previous: {context_prev}\nTarget: {text}\nNext: {context_next}\nKhmer Translation:"
        else:
            prompt += f"Source Text: {text}\nKhmer Translation:"

        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }

        try:
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                return res.json().get("response", "").strip()
            return f"[Ollama Error {res.status_code}]"
        except Exception as e:
            return f"[Ollama Connection Error: {str(e)}]"

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "Chinese",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        temperature: float = 0.3
    ) -> List[str]:
        return [self.translate(t, source_lang, target_lang, prompt_template, temperature=temperature) for t in texts]
