from typing import Optional
from ..database.sqlite import DatabaseManager

class CacheManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_translation(self, text: str, source_lang: str = "zh", target_lang: str = "km") -> Optional[str]:
        return self.db.get_cached_translation(text, source_lang, target_lang)

    def set_translation(self, src_text: str, tgt_text: str, source_lang: str = "zh", target_lang: str = "km", provider: str = "Gemini"):
        self.db.save_cached_translation(src_text, tgt_text, source_lang, target_lang, provider)
