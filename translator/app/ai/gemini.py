import os
import json
import re
import time
import mimetypes
import requests
from typing import List, Optional, Dict, Any
from .base import BaseAIProvider
from .deepl import GoogleTranslateProvider

GEMINI_TRANSCRIBE_PROMPT = """You are a professional subtitle transcription engine for movies and TV dramas.
Transcribe ALL spoken dialogue in this audio verbatim, in the language actually spoken (do not translate it).
Segment the transcript into natural subtitle lines the way closed captions are segmented — split on speech
pauses, each line one complete thought, preserve names and emotional expressions exactly as spoken.

Output STRICTLY in this format, one subtitle per line, nothing else (no headers, no explanations, no markdown):
[HH:MM:SS.mmm --> HH:MM:SS.mmm] transcribed text
"""


# Brand-new free-tier projects often don't have the newest models allow-listed yet
# (Google rolls access out gradually) — a 404 "model not found" on gemini-2.5-* is
# usually that, not a bad key. Gemini's free-tier quota is also tracked PER MODEL,
# not shared — a 429 on gemini-2.5-flash doesn't mean gemini-2.0-flash is exhausted
# too, it's a separate pool. So the same chain handles both: auto-fallback to an
# older, less-contended model on 404 OR 429 instead of surfacing a confusing failure
# or burning through every rotated key for nothing.
MODEL_FALLBACK_CHAIN = {
    "gemini-2.5-flash": ["gemini-2.0-flash", "gemini-flash-latest"],
    "gemini-2.5-pro": ["gemini-2.0-flash", "gemini-pro-latest"],
    "gemini-2.0-flash": ["gemini-flash-latest"],
    "gemini-2.0-pro": ["gemini-pro-latest"],
}
_FALLBACK_TRIGGER_CODES = (404, 429)


def _post_generate_content(raw_key: str, model_name: str, payload: dict, timeout: int = 20):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={raw_key}"
    return requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=timeout)


def _generate_with_model_fallback(raw_key: str, requested_model: str, payload: dict, timeout: int = 20):
    """POST generateContent, automatically retrying with older models on 404 (model
    not available for this key/project) or 429 (that model's quota exhausted —
    other models on the same key often still have headroom). Returns (response, model_used)."""
    res = _post_generate_content(raw_key, requested_model, payload, timeout)
    if res.status_code not in _FALLBACK_TRIGGER_CODES:
        return res, requested_model

    for fallback_model in MODEL_FALLBACK_CHAIN.get(requested_model, []):
        res = _post_generate_content(raw_key, fallback_model, payload, timeout)
        if res.status_code not in _FALLBACK_TRIGGER_CODES:
            return res, fallback_model

    return res, requested_model


def parse_gemini_transcript(raw_text: str) -> List[Dict[str, Any]]:
    """Parse Gemini's `[HH:MM:SS.mmm --> HH:MM:SS.mmm] text` transcript lines into segments."""
    pattern = re.compile(
        r'\[(\d{2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{1,3})\]\s*(.+)'
    )
    segments = []
    for line in (raw_text or "").splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2, text = m.groups()
        text = text.strip()
        if not text:
            continue
        start_ms = (int(h1) * 3600 + int(m1) * 60 + int(s1)) * 1000 + int(ms1.ljust(3, "0")[:3])
        end_ms = (int(h2) * 3600 + int(m2) * 60 + int(s2)) * 1000 + int(ms2.ljust(3, "0")[:3])
        if end_ms > start_ms:
            segments.append({"start_ms": start_ms, "end_ms": end_ms, "text": text})
    return segments

NETFLIX_MASTER_PROMPT = """You are an expert AI localization system for TV dramas and movies, Chinese or English source (ប្រព័ន្ធបកប្រែ និងសម្រួលរឿងភាគចិន/ភាសាអង់គ្លេសកម្រិត Netflix/iQIYI).
Your mission is to produce professional source-to-Khmer subtitles and audio dubbing scripts comparable to official Cambodian TV dubbing quality. The exact source language is given per request — translate naturally from whichever language is specified, not only Chinese.

Your workflow must always be:
1. Analyze surrounding context (5-7 dialogue lines).
2. Detect speaker, relationship (lovers, master/disciple, CEO/servant, parents/children, enemies...), and emotion (angry, crying, romantic, threatening, sarcastic, arrogant, respectful...).
3. Check glossary & terminology for the SOURCE LANGUAGE actually given in the request:

   If source is Chinese:
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

   If source is English:
   - Sir / Boss -> លោក
   - Ma'am / Madam -> លោកស្រី
   - Mr. [Name] -> លោក [ឈ្មោះ]
   - Mrs./Ms. [Name] -> លោកស្រី [ឈ្មោះ]
   - Dad / Father -> ប៉ា
   - Mom / Mother -> ម៉ាក់
   - Honey / Darling -> ស្រលាញ់ / ទីស្រលាញ់ (romantic context only)
   - Officer -> លោកប៉ូលិស
   - Doctor -> គ្រូពេទ្យ

4. Never translate word-for-word. Never sound like machine translation or Google Translate.
5. Rewrite dialogue naturally into authentic spoken Khmer as if it were originally written in Khmer.
6. Keep sentences short and punchy for TV audio dubbing lip-sync.

FEW-SHOT EXAMPLES (Chinese source):
你疯了吗？ -> ឯងឆ្កួតហើយឬ?
滚！ -> ចេញទៅ!
你敢！ -> ឯងហ៊ានណាស់!
够了！ -> ល្មមបានហើយ!
闭嘴！ -> បិទមាត់ទៅ!
你骗人！ -> ឯងកុហកខ្ញុំ!
我不会放过你！ -> ខ្ញុំមិនលើកលែងឯងទេ!
谢谢你 -> អរគុណណាស់
对不起 -> ខ្ញុំសុំទោស

FEW-SHOT EXAMPLES (English source — same target register/naturalness, not a literal translation):
You're crazy, aren't you? -> ឯងឆ្កួតហើយឬ?
Get out! -> ចេញទៅ!
How dare you! -> ឯងហ៊ានណាស់!
That's enough! -> ល្មមបានហើយ!
Shut up! -> បិទមាត់ទៅ!
You're lying! -> ឯងកុហកខ្ញុំ!
I won't let you off the hook! -> ខ្ញុំមិនលើកលែងឯងទេ!
Thank you so much -> អរគុណណាស់
I'm sorry -> ខ្ញុំសុំទោស

STRICT OUTPUT RULES:
- Return ONLY the final clean Khmer subtitle.
- NEVER use period '.' or Khmer full stop '។' (Khan) at the end or inside subtitles. Omit period '.' and '។' completely.
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
15. NEVER use period '.' or Khmer full stop '។' (Khan). Remove all '.' and '។' from Khmer subtitles to keep captions clean.
16. Return ONLY the improved Khmer subtitle.

Example:

Original:
ខ្ញុំមិនអាចទទួលយករឿងនេះបានទេ។

Improved:
ខ្ញុំមិនអាចទទួលយកបានទេ

Original:
អ្នកកំពុងនិយាយអ្វី?

Improved:
ឯងកំពុងនិយាយអីហ្នឹង

Original:
សូមអរគុណចំពោះការជួយរបស់អ្នក។

Improved:
អរគុណដែលជួយខ្ញុំ
"""

def clean_khmer_translation(raw_text: str) -> str:
    """Post-processor to extract pure Khmer script from LLM output, removing any English notes, markdown, or messy dots/khan."""
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

    # 6. Clean leading/trailing punctuation, messy period (.) and Khmer full stop (។)
    text = text.replace("។", "").replace(".", "")
    text = re.sub(r'^[/:,\-\s]+', '', text)
    text = re.sub(r'[/:\-\s]+$', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # If nothing but stray punctuation survived the stripping (e.g. the model's line
    # was an English refusal/note like "(no dialogue)" and step 5 ate the words,
    # leaving just ")"), this isn't a usable translation — signal failure instead of
    # silently saving garbage into the subtitle.
    if not re.search(r'[ក-៿]', text):
        return ""

    return text


from ..database.sqlite import DatabaseManager
from ..utils.crypto import decrypt_api_key

def test_gemini_key(raw_api_key: str, model_name: str = "gemini-2.5-flash") -> tuple[bool, str, int, str]:
    """Tests a single Gemini API key and measures response time in ms.
    Returns (success, status, elapsed_ms, detail) — `detail` carries the actual
    HTTP status/response so a real cause (bad key vs. quota vs. model not
    available on this key/project vs. network error) doesn't get flattened
    into a single misleading "Invalid" label."""
    if not raw_api_key:
        return False, "Invalid", 0, "No API key provided."

    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Ping"}]}],
        "generationConfig": {"maxOutputTokens": 5}
    }
    start_t = time.time()
    try:
        res, model_used = _generate_with_model_fallback(raw_api_key, model_name, payload, timeout=10)
        elapsed_ms = int((time.time() - start_t) * 1000)
        fallback_note = "" if model_used == model_name else f" (auto-fell back to {model_used} — {model_name} was unavailable or out of quota on this key/project)"
        if res.status_code == 200:
            return True, "Working", elapsed_ms, f"OK{fallback_note}"
        elif res.status_code == 429:
            return False, "Quota Exceeded", elapsed_ms, f"429 Rate/Quota Limit: {res.text[:300]}"
        elif res.status_code == 403:
            return False, "Quota Exceeded", elapsed_ms, f"403 Forbidden (quota, billing, or API not enabled for this project): {res.text[:300]}"
        elif res.status_code == 404:
            return False, "Model Unavailable", elapsed_ms, f"404 — none of '{model_name}' or its fallback models are available for this key's project: {res.text[:300]}"
        elif res.status_code == 400:
            return False, "Invalid", elapsed_ms, f"400 Bad Request (often API_KEY_INVALID — check for extra spaces/newlines when pasting): {res.text[:300]}"
        else:
            return False, "Invalid", elapsed_ms, f"{res.status_code}: {res.text[:300]}"
    except Exception as e:
        elapsed_ms = int((time.time() - start_t) * 1000)
        return False, "Invalid", elapsed_ms, f"Network/exception error: {str(e)}"


class GeminiProvider(BaseAIProvider):
    _round_robin_idx = 0

    def __init__(self, api_key: str = "", model_name: str = "gemini-2.5-flash", db: Optional[DatabaseManager] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.db = db
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
        raw_translation = self._call_gemini_api_with_rotation(system_prompt, user_content, temperature)
        if not raw_translation or raw_translation.startswith("Error") or raw_translation.startswith("API Exception") or raw_translation == "No available Gemini API key.":
            return self.fallback_provider.translate(text, source_lang, target_lang)

        cleaned_khmer = clean_khmer_translation(raw_translation)
        if not cleaned_khmer:
            # The model's line had no real Khmer left after cleanup (refusal, note-only
            # reply, etc.) — fall back instead of saving stray punctuation as the subtitle.
            return self.fallback_provider.translate(text, source_lang, target_lang)

        # Phase 2: Senior Khmer Screenplay Writer Polish Pass (AI Quality Review)
        if cleaned_khmer and len(cleaned_khmer) > 2:
            polished = self.polish_khmer_dialogue(cleaned_khmer, context_prev, context_next)
            if polished:
                return polished

        return cleaned_khmer

    def polish_khmer_dialogue(self, draft_khmer: str, context_prev: str = "", context_next: str = "") -> str:
        """Phase 2 VoxCPM2 Khmer Naturalization & Localization Pass."""
        user_content = f"Input Khmer:\n{draft_khmer}\n\nOutput:"
        res = self._call_gemini_api_with_rotation(VOXCPM2_KHMER_LOCALIZER_PROMPT, user_content, temperature=0.2)
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

        system_prompt = prompt_template or NETFLIX_MASTER_PROMPT
        user_content = f"Translate the following list of subtitle lines from {source_lang} to natural spoken {target_lang}:\n\n"
        for idx, t in enumerate(texts, 1):
            user_content += f"{idx}. {t}\n"
        user_content += "\nReturn JSON array of strings corresponding to translated lines."

        res_raw = self._call_gemini_api_with_rotation(system_prompt, user_content, temperature)
        if not res_raw or res_raw.startswith("Error") or res_raw == "No available Gemini API key.":
            return self.fallback_provider.translate_batch(texts, source_lang, target_lang)

        try:
            cleaned = res_raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) == len(texts):
                return [clean_khmer_translation(str(x)) for x in parsed]
        except Exception:
            pass

        return [self.translate(t, source_lang, target_lang, prompt_template, temperature=temperature) for t in texts]

    def transcribe_audio(self, audio_path: str, language: Optional[str] = None, progress_cb=None) -> List[Dict[str, Any]]:
        """Transcribe an audio file using Gemini's multimodal audio understanding.
        Uploads via the File API (works for full-length movie audio, not just short
        clips), then asks for a timestamped transcript and parses it into segments.
        Uses the same multi-key rotation as translation — one key hitting quota
        automatically falls through to the next."""
        candidates = self._get_key_candidates()
        if not candidates:
            raise RuntimeError("No available Gemini API key.")

        last_error = ""
        for key_item in candidates:
            raw_key = decrypt_api_key(key_item["api_key_encrypted"])
            if not raw_key:
                continue
            try:
                if progress_cb:
                    progress_cb(15, "Uploading audio to Gemini...")
                file_uri, mime_type = self._upload_audio_file(audio_path, raw_key)

                if progress_cb:
                    progress_cb(35, "Gemini is processing the audio...")
                self._wait_file_active(file_uri, raw_key)

                if progress_cb:
                    progress_cb(50, "Transcribing with Gemini...")
                prompt = GEMINI_TRANSCRIBE_PROMPT
                if language:
                    prompt += f"\nThe spoken language is: {language}."

                payload = {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {"file_data": {"file_uri": file_uri, "mime_type": mime_type}},
                            {"text": prompt}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 65536}
                }
                res, _model_used = _generate_with_model_fallback(raw_key, self.model_name, payload, timeout=600)

                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    if self.db and key_item.get("id", -1) != -1:
                        self.db.update_gemini_key_stats(key_item["id"], status="Working")
                    segments = parse_gemini_transcript(text)
                    if not segments:
                        raise RuntimeError("Gemini returned no parseable subtitle lines.")
                    return segments

                elif res.status_code in (429, 403):
                    last_error = f"Error {res.status_code}: Quota/Rate Limit"
                    if self.db and key_item.get("id", -1) != -1:
                        self.db.update_gemini_key_stats(key_item["id"], status="Quota Exceeded")
                    continue
                else:
                    last_error = f"Error {res.status_code}: {res.text[:200]}"
                    continue

            except Exception as e:
                last_error = str(e)
                continue

        raise RuntimeError(last_error or "Gemini transcription failed on all available keys.")

    @staticmethod
    def _upload_audio_file(audio_path: str, api_key: str):
        """Resumable upload to the Gemini File API. Returns (file_uri, mime_type)."""
        mime_type = mimetypes.guess_type(audio_path)[0] or "audio/wav"
        file_size = os.path.getsize(audio_path)
        display_name = os.path.basename(audio_path)

        start_res = requests.post(
            f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}",
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(file_size),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "Content-Type": "application/json"
            },
            json={"file": {"display_name": display_name}},
            timeout=30
        )
        start_res.raise_for_status()
        upload_url = start_res.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise RuntimeError("Gemini File API did not return an upload URL.")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        upload_res = requests.post(
            upload_url,
            headers={
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
                "Content-Length": str(file_size)
            },
            data=audio_bytes,
            timeout=300
        )
        upload_res.raise_for_status()
        file_info = upload_res.json().get("file", {})
        file_uri = file_info.get("uri")
        if not file_uri:
            raise RuntimeError("Gemini File API upload did not return a file URI.")
        return file_uri, mime_type

    @staticmethod
    def _wait_file_active(file_uri: str, api_key: str, timeout_s: int = 120):
        """Poll until the uploaded file finishes server-side processing."""
        file_name = file_uri.split("/files/")[-1]
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            res = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/files/{file_name}?key={api_key}",
                timeout=15
            )
            if res.status_code == 200:
                state = res.json().get("state", "")
                if state == "ACTIVE":
                    return
                if state == "FAILED":
                    raise RuntimeError("Gemini failed to process the uploaded audio file.")
            time.sleep(2)
        raise RuntimeError("Timed out waiting for Gemini to process the uploaded audio file.")

    def _get_key_candidates(self) -> List[Dict[str, Any]]:
        """Retrieve key candidates according to Load Balancing Mode."""
        if not self.db:
            if self.api_key:
                return [{"id": -1, "name": "Direct Key", "api_key_encrypted": self.api_key, "status": "Working", "response_time_ms": 0}]
            return []

        keys = self.db.get_gemini_keys(enabled_only=True)
        if not keys:
            if self.api_key:
                return [{"id": -1, "name": "Direct Key", "api_key_encrypted": self.api_key, "status": "Working", "response_time_ms": 0}]
            return []

        # Filter out known invalid keys, but allow Quota Exceeded if no working keys remain
        working_keys = [k for k in keys if k.get("status") in ("Working", "Quota Exceeded", "Unknown", None)]
        if not working_keys:
            working_keys = keys

        mode = self.db.get_setting("load_balancing_mode", "Sequential")

        if mode == "Round Robin" and len(working_keys) > 1:
            GeminiProvider._round_robin_idx = (GeminiProvider._round_robin_idx + 1) % len(working_keys)
            # Reorder list starting from round robin index
            idx = GeminiProvider._round_robin_idx
            return working_keys[idx:] + working_keys[:idx]

        elif mode == "Fastest Response":
            # Sort keys by response_time_ms (putting non-zero lowest latency first)
            def sort_key(k):
                ms = k.get("response_time_ms", 0)
                return ms if ms > 0 else 999999
            return sorted(working_keys, key=sort_key)

        else:  # Sequential (default)
            return working_keys

    def _call_gemini_api_with_rotation(self, system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        candidates = self._get_key_candidates()
        if not candidates:
            return "No available Gemini API key."

        last_error = ""
        for key_item in candidates:
            raw_key = decrypt_api_key(key_item["api_key_encrypted"])
            if not raw_key:
                continue

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

            start_t = time.time()
            try:
                res, _model_used = _generate_with_model_fallback(raw_key, self.model_name, payload, timeout=20)
                elapsed_ms = int((time.time() - start_t) * 1000)

                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if self.db and key_item.get("id", -1) != -1:
                        self.db.update_gemini_key_stats(key_item["id"], status="Working", response_time_ms=elapsed_ms)
                    return text

                elif res.status_code in (429, 403):
                    last_error = f"Error {res.status_code}: Quota/Rate Limit"
                    if self.db and key_item.get("id", -1) != -1:
                        self.db.update_gemini_key_stats(key_item["id"], status="Quota Exceeded", response_time_ms=elapsed_ms)
                    # Silently continue to next candidate key!
                    continue

                else:
                    last_error = f"Error {res.status_code}: {res.text}"
                    if self.db and key_item.get("id", -1) != -1:
                        self.db.update_gemini_key_stats(key_item["id"], status="Invalid", response_time_ms=elapsed_ms)
                    continue

            except Exception as e:
                elapsed_ms = int((time.time() - start_t) * 1000)
                last_error = f"API Exception: {str(e)}"
                if self.db and key_item.get("id", -1) != -1:
                    self.db.update_gemini_key_stats(key_item["id"], status="Invalid", response_time_ms=elapsed_ms)
                continue

        if last_error:
            return f"No available Gemini API key. ({last_error})"
        return "No available Gemini API key."

