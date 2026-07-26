import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from app.ai.gemini import GeminiProvider

chinese_sample = [
    "传说不是当公主 这是当王",
    "大婚日让他们来买死人",
    "侯爷真会挑时候",
    "少说两句吧"
]

print("Testing Translation (Gemini with auto-fallback to Google Translate)...")
provider = GeminiProvider(api_key="")

for line in chinese_sample:
    khmer = provider.translate(line, source_lang="Chinese", target_lang="Khmer")
    print(f"  CN: {line}")
    print(f"  KM: {khmer}\n")
