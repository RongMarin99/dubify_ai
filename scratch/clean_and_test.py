import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "translator"))

from app.database.sqlite import DatabaseManager
from app.core.cache import CacheManager
from app.ai.gemini import GeminiProvider

db = DatabaseManager()
cache_mgr = CacheManager(db)

# Verify bad cache is deleted
bad_check = db.get_cached_translation("传说不是当公主 这是当王")
print("Cached translation for test line:", repr(bad_check))

provider = GeminiProvider(api_key="")
res = provider.translate("传说不是当公主 这是当王", source_lang="Chinese", target_lang="Khmer")
print("New Fresh Translation:", res)
