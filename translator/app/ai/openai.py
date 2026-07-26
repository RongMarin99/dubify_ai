import os
import json
import requests
from typing import List, Optional
from .base import BaseAIProvider
from .deepl import GoogleTranslateProvider

class OpenAIProvider(BaseAIProvider):
    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1", model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.fallback_provider = GoogleTranslateProvider()

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

        if not self.api_key:
            return self.fallback_provider.translate(text, source_lang, target_lang)

        system_prompt = prompt_template or f"You are a professional subtitle translator. Translate from {source_lang} to natural spoken {target_lang}. Return ONLY the translation."
        user_content = text
        if context_prev or context_next:
            user_content = f"Previous line: {context_prev}\nTarget line: {text}\nNext line: {context_next}\nTranslate ONLY the target line to {target_lang}."

        res = self._request(system_prompt, user_content, temperature)
        if not res or res.startswith("Error"):
            return self.fallback_provider.translate(text, source_lang, target_lang)
        return res

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "Chinese",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        temperature: float = 0.3
    ) -> List[str]:
        results = []
        for t in texts:
            results.append(self.translate(t, source_lang, target_lang, prompt_template, temperature=temperature))
        return results

    def _request(self, system_prompt: str, user_content: str, temperature: float) -> str:
        if not self.api_key:
            return ""

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": temperature
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            return f"Error: {res.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"
