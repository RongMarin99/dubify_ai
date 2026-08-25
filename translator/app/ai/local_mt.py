import os
from typing import List, Optional, Dict, Tuple
from .base import BaseAIProvider

# FLORES-200 language codes NLLB expects. Covers the source languages this app
# already offers (see main_window.py lang_names) plus Khmer as the fixed target.
LANG_TO_FLORES = {
    "English": "eng_Latn",
    "Chinese": "zho_Hans",
    "Japanese": "jpn_Jpan",
    "Korean": "kor_Hang",
    "Khmer": "khm_Khmr",
}

DEFAULT_BASE_MODEL = "facebook/nllb-200-distilled-600M"
# Where finetune_nllb_km.py saves the fine-tuned checkpoint. If it isn't there
# yet, LocalNLLBProvider transparently falls back to the pretrained base model
# (still supports Khmer out of the box, just less tuned for subtitle register).
DEFAULT_FINETUNED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "models", "nllb-en-km-finetuned"
)

# One (tokenizer, model, device) per resolved model path, shared across
# provider instances/translate calls within the process — reloading NLLB
# per subtitle line would dominate runtime.
_MODEL_CACHE: Dict[str, Tuple] = {}


def _resolve_model_path(model_path: Optional[str]) -> str:
    if model_path and os.path.isdir(model_path):
        return model_path
    if os.path.isdir(DEFAULT_FINETUNED_DIR):
        return DEFAULT_FINETUNED_DIR
    return DEFAULT_BASE_MODEL


class LocalNLLBProvider(BaseAIProvider):
    """Offline English/Chinese/Japanese/Korean -> Khmer translation using a local
    NLLB-200 model (optionally fine-tuned on SeyhaLite/Translate-English-Khmer-All).
    No network calls, no API key, no rate limit — runs entirely on this machine."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = _resolve_model_path(model_path)

    def _get_model(self):
        if self.model_path in _MODEL_CACHE:
            return _MODEL_CACHE[self.model_path]

        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)
        model.eval()

        _MODEL_CACHE[self.model_path] = (tokenizer, model, device)
        return tokenizer, model, device

    def _generate(self, texts: List[str], source_lang: str, target_lang: str) -> List[str]:
        import torch

        tokenizer, model, device = self._get_model()
        src_code = LANG_TO_FLORES.get(source_lang, "eng_Latn")
        tgt_code = LANG_TO_FLORES.get(target_lang, "khm_Khmr")

        tokenizer.src_lang = src_code
        inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True).to(device)
        forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_code)

        with torch.no_grad():
            generated = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=256,
                num_beams=4,
            )
        return [t.strip() for t in tokenizer.batch_decode(generated, skip_special_tokens=True)]

    def translate(
        self,
        text: str,
        source_lang: str = "English",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        context_prev: str = "",
        context_next: str = "",
        temperature: float = 0.3,
    ) -> str:
        # NLLB is a direct MT model, not instructable — prompt_template/context/
        # temperature don't apply here and are accepted only for interface parity
        # with the other BaseAIProvider implementations.
        if not text.strip():
            return ""
        try:
            return self._generate([text], source_lang, target_lang)[0]
        except Exception as e:
            return f"[Local NLLB Error: {str(e)}]"

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "English",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        temperature: float = 0.3,
    ) -> List[str]:
        if not texts:
            return []
        try:
            return self._generate(texts, source_lang, target_lang)
        except Exception as e:
            return [f"[Local NLLB Error: {str(e)}]" for _ in texts]
