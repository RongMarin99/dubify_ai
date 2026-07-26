from typing import List, Optional
from PySide6.QtCore import QThread, Signal
from ..model.models import SubtitleItem
from ..ai.base import BaseAIProvider
from ..ai.gemini import GeminiProvider
from ..ai.openai import OpenAIProvider
from ..ai.ollama import OllamaProvider
from ..ai.deepl import GoogleTranslateProvider
from ..core.cache import CacheManager

class TranslationWorker(QThread):
    progress = Signal(int, str)  # progress %, status msg
    line_translated = Signal(int, str)  # sub_index, tgt_text
    finished = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        subtitles: List[SubtitleItem],
        engine_name: str = "Gemini",
        api_key: str = "",
        model_name: str = "gemini-2.5-flash",
        custom_prompt: str = "",
        use_cache: bool = True,
        cache_mgr: Optional[CacheManager] = None
    ):
        super().__init__()
        self.subtitles = subtitles
        self.engine_name = engine_name
        self.api_key = api_key
        self.model_name = model_name
        self.custom_prompt = custom_prompt
        self.use_cache = use_cache
        self.cache_mgr = cache_mgr

    def run(self):
        try:
            total = len(self.subtitles)
            if total == 0:
                self.finished.emit([])
                return

            provider = self._create_provider()

            translated_subs = []
            for idx, item in enumerate(self.subtitles):
                if not item.src_text.strip():
                    translated_subs.append(item)
                    continue

                # Check Cache first if enabled
                cached_text = None
                if self.use_cache and self.cache_mgr:
                    cached_text = self.cache_mgr.get_translation(item.src_text)

                if cached_text:
                    item.tgt_text = cached_text
                    item.status = "Translated"
                else:
                    # Extended 5-7 Line Sliding Context Window Extraction
                    prev_items = self.subtitles[max(0, idx - 3):idx]
                    next_items = self.subtitles[idx + 1:min(total, idx + 4)]

                    prev_context = "\n".join([f"{i+1}. {s.src_text}" for i, s in enumerate(prev_items)])
                    next_context = "\n".join([f"{i+1}. {s.src_text}" for i, s in enumerate(next_items)])

                    khmer_translation = provider.translate(
                        text=item.src_text,
                        source_lang="Chinese",
                        target_lang="Khmer",
                        prompt_template=self.custom_prompt,
                        context_prev=prev_context,
                        context_next=next_context
                    )

                    item.tgt_text = khmer_translation
                    item.status = "Translated"

                    # Save to Cache
                    if self.use_cache and self.cache_mgr and khmer_translation:
                        self.cache_mgr.set_translation(item.src_text, khmer_translation, provider=self.engine_name)

                translated_subs.append(item)
                self.line_translated.emit(item.id, item.tgt_text)

                pct = int((idx + 1) / total * 100)
                self.progress.emit(pct, f"Translated line {idx+1}/{total}...")

            self.progress.emit(100, "Translation Complete!")
            self.finished.emit(translated_subs)

        except Exception as e:
            self.failed.emit(str(e))

    def _create_provider(self) -> BaseAIProvider:
        if self.engine_name == "Gemini":
            return GeminiProvider(api_key=self.api_key, model_name=self.model_name)
        elif self.engine_name in ["OpenAI", "DeepSeek"]:
            return OpenAIProvider(api_key=self.api_key, model_name=self.model_name)
        elif self.engine_name == "Ollama":
            return OllamaProvider(model_name=self.model_name)
        else:
            return GoogleTranslateProvider()
