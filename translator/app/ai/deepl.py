import requests
import urllib.parse
from typing import List, Optional
from .base import BaseAIProvider

class GoogleTranslateProvider(BaseAIProvider):
    """Free Google Translate web API integration as instant fallback."""
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

        # Language code mapping
        lang_map = {
            "Chinese": "zh-CN", "Khmer": "km", "English": "en",
            "Japanese": "ja", "Korean": "ko"
        }
        sl = lang_map.get(source_lang, "auto")
        tl = lang_map.get(target_lang, "km")

        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={urllib.parse.quote(text)}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                translated_chunks = [chunk[0] for chunk in data[0] if chunk[0]]
                return "".join(translated_chunks).strip()
            return f"[Google Trans Error {res.status_code}]"
        except Exception as e:
            return f"[Translate Exception: {str(e)}]"

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "Chinese",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        temperature: float = 0.3
    ) -> List[str]:
        return [self.translate(t, source_lang, target_lang) for t in texts]
