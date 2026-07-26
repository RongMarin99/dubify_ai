from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseAIProvider(ABC):
    @abstractmethod
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
        """Translate a single line of text with optional context."""
        pass

    @abstractmethod
    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "Chinese",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        temperature: float = 0.3
    ) -> List[str]:
        """Translate a list of subtitle strings in batch mode."""
        pass
