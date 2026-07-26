import os
import json
import re
import requests
from typing import List, Optional
from .base import BaseAIProvider
from .deepl import GoogleTranslateProvider

NETFLIX_MASTER_PROMPT = """You are an expert AI localization system for Chinese TV dramas (ប្រព័ន្ធបកប្រែ និងសម្រួលរឿងភាគចិនកម្រិត Netflix/iQIYI).
Your mission is to produce professional Chinese-to-Khmer subtitles and audio dubbing scripts comparable to official Cambodian TV dubbing quality.

Your workflow must always be:
1. Analyze surrounding context (5-7 dialogue lines).
2. Detect speaker, relationship (lovers, master/disciple, CEO/servant, parents/children, enemies...), and emotion (angry, crying, romantic, threatening, sarcastic, arrogant, respectful...).
3. Check glossary & terminology:
   - 董事长 -> ប្រធានក្រុមហ៊ុន
   - 总裁 -> អគ្គនាយក
   - 少爷 -> លោកម្ចាស់
   - 小姐 -> អ្នកនាង
   - 夫人 -> លោកស្រី
   - 老爷 -> លោកម្ចាស់ធំ
   - 师父 -> លោកគ្រូ
   - 师兄 -> បងសិស្ស
   - 师弟 -> ប្អូនសិស្ស
   - 师妹 -> ប្អូនស្រីសិស្ស
   - 侯爷 -> លោក ហ៊ូ
4. Never translate word-for-word. Never sound like machine translation or Google Translate.
5. Rewrite dialogue naturally into authentic spoken Khmer as if it were originally written in Khmer.
6. Keep sentences short and punchy for TV audio dubbing lip-sync.

FEW-SHOT EXAMPLES:
你疯了吗？ -> ឯងឆ្កួតហើយឬ?
滚！ -> ចេញទៅ!
你敢！ -> ឯងហ៊ានណាស់!
够了！ -> ល្មមបានហើយ!
闭嘴！ -> បិទមាត់ទៅ!
你骗人！ -> ឯងកុហកខ្ញុំ!
我不会放过你！ -> ខ្ញុំមិនលើកលែងឯងទេ!
谢谢你 -> អរគុណណាស់
对不起 -> ខ្ញុំសុំទោស

STRICT OUTPUT RULES:
- Return ONLY the final clean Khmer subtitle.
- No explanation, no English, no Chinese, no parentheses, no markdown.
"""

VOXCPM2_KHMER_LOCALIZER_PROMPT = """You are VoxCPM2, an expert Khmer localization editor and dialogue writer.

Your task is NOT to translate.

Your task is to rewrite the provided Khmer subtitle into natural, fluent, and emotionally appropriate Khmer suitable for TV dramas and movie dubbing.

Requirements:

1. Keep the original meaning exactly.
2. Preserve the speaker's emotion.
3. Preserve the relationship between characters.
4. Make the dialogue sound like native Cambodian Khmer.
5. Remove any robotic or machine-translated wording.
6. Use natural spoken Khmer instead of formal written Khmer.
7. Never translate word-for-word.
8. Keep names unchanged.
9. Keep important terms consistent.
10. Make the subtitle suitable for voice dubbing.
11. Keep subtitles concise and easy to read.
12. Maximum two subtitle lines.
13. Do not add or remove important information.
14. If the sentence already sounds natural, return it unchanged.
15. Return ONLY the improved Khmer subtitle.

Example:

Original:
ខ្ញុំមិនអាចទទួលយករឿងនេះបានទេ។

Improved:
ខ្ញុំមិនអាចទទួលយកបានទេ!

Original:
អ្នកកំពុងនិយាយអ្វី?

Improved:
ឯងកំពុងនិយាយអីហ្នឹង?

Original:
សូមអរគុណចំពោះការជួយរបស់អ្នក។

Improved:
អរគុណដែលជួយខ្ញុំ។
"""

def clean_khmer_translation(raw_text: str) -> str:
    """Post-processor to extract pure Khmer script from LLM output, removing any English notes or markdown."""
    if not raw_text:
        return ""

    text = raw_text.strip()

    # 1. Take final line if LLM returned multi-line reasoning
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        khmer_lines = [l for l in lines if re.search(r'[\u1780-\u17FF]', l)]
        if khmer_lines:
            text = khmer_lines[-1]
        else:
            text = lines[-1]

    # 2. If there's an arrow mapping "A -> B", take B
    if "->" in text:
        text = text.split("->")[-1].strip()

    # 3. Remove text inside parentheses / brackets / braces
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\{.*?\}', '', text)

    # 4. Remove markdown formatting, quotes, backticks
    text = text.replace("**", "").replace("*", "").replace('"', '').replace("'", '').replace('`', '')

    # 5. Remove any leftover English words or romanizations
    text = re.sub(r'\b[A-Za-z0-9_]{2,}\b', '', text)

    # 6. Clean leading/trailing punctuation and extra whitespace
    text = re.sub(r'^[/:,\-\s\.]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text


class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str = "", model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
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

        system_prompt = prompt_template or NETFLIX_MASTER_PROMPT

        user_content = f"Source Language: {source_lang}\nTarget Language: {target_lang}\n\n"
        if context_prev or context_next:
            user_content += f"=== PREVIOUS DIALOGUES ===\n{context_prev}\n\n"
            user_content += f"=== CURRENT TARGET DIALOGUE TO TRANSLATE ===\n{text}\n\n"
            user_content += f"=== NEXT DIALOGUES ===\n{context_next}\n\n"
            user_content += "Translate ONLY the 'CURRENT TARGET DIALOGUE TO TRANSLATE'. Output ONLY the clean Khmer text."
        else:
            user_content += f"Target Dialogue: {text}"

        # Phase 1: Context & Relationship Aware Localization Pass
        raw_translation = self._call_gemini_api(system_prompt, user_content, temperature)
        if not raw_translation or raw_translation.startswith("Error") or raw_translation.startswith("API Exception"):
            return self.fallback_provider.translate(text, source_lang, target_lang)

        cleaned_khmer = clean_khmer_translation(raw_translation)

        # Phase 2: Senior Khmer Screenplay Writer Polish Pass (AI Quality Review)
        if cleaned_khmer and len(cleaned_khmer) > 2:
            polished = self.polish_khmer_dialogue(cleaned_khmer, context_prev, context_next)
            if polished:
                return polished

        return cleaned_khmer

    def polish_khmer_dialogue(self, draft_khmer: str, context_prev: str = "", context_next: str = "") -> str:
        """Phase 2 VoxCPM2 Khmer Naturalization & Localization Pass."""
        user_content = f"Input Khmer:\n{draft_khmer}\n\nOutput:"
        res = self._call_gemini_api(VOXCPM2_KHMER_LOCALIZER_PROMPT, user_content, temperature=0.2)
        cleaned = clean_khmer_translation(res)
        return cleaned if cleaned else draft_khmer

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "Chinese",
        target_lang: str = "Khmer",
        prompt_template: Optional[str] = None,
        temperature: float = 0.3
    ) -> List[str]:
        if not texts:
            return []

        if not self.api_key:
            return self.fallback_provider.translate_batch(texts, source_lang, target_lang)

        system_prompt = prompt_template or NETFLIX_MASTER_PROMPT
        user_content = f"Translate the following list of subtitle lines from {source_lang} to natural spoken {target_lang}:\n\n"
        for idx, t in enumerate(texts, 1):
            user_content += f"{idx}. {t}\n"
        user_content += "\nReturn JSON array of strings corresponding to translated lines."

        res_raw = self._call_gemini_api(system_prompt, user_content, temperature)
        if not res_raw or res_raw.startswith("Error"):
            return self.fallback_provider.translate_batch(texts, source_lang, target_lang)

        try:
            cleaned = res_raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) == len(texts):
                return [clean_khmer_translation(str(x)) for x in parsed]
        except Exception:
            pass

        return [self.translate(t, source_lang, target_lang, prompt_template, temperature=temperature) for t in texts]

    def _call_gemini_api(self, system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\nTask:\n{user_content}"}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 300
            }
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text
            else:
                return f"Error {res.status_code}: {res.text}"
        except Exception as e:
            return f"API Exception: {str(e)}"
