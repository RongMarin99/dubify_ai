import os
import sys

# Add translator to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from translator.app.utils.crypto import encrypt_api_key, decrypt_api_key, mask_api_key
from translator.app.database.sqlite import DatabaseManager
from translator.app.ai.local_models import LocalModelManager
from translator.app.ai.gemini import GeminiProvider

def test_all():
    print("=== 1. Testing Crypto ===")
    raw = "AIzaSyDummyTestKey123456789"
    enc = encrypt_api_key(raw)
    dec = decrypt_api_key(enc)
    masked = mask_api_key(raw)
    
    assert enc.startswith("enc:v1:"), "Encryption marker missing"
    assert dec == raw, "Decryption mismatch"
    assert masked.startswith("AIzaSy"), "Masking mismatch"
    print(f"Original: {raw}")
    print(f"Encrypted: {enc}")
    print(f"Decrypted: {dec}")
    print(f"Masked: {masked}")
    print("[OK] Crypto tests passed.")

    print("\n=== 2. Testing Database Key Manager ===")
    test_db_path = "test_ai_manager.db"
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    db = DatabaseManager(test_db_path)
    key_id1 = db.add_gemini_key("Primary Key", "AIzaSyKey111111111", status="Working", enabled=True)
    key_id2 = db.add_gemini_key("Backup Key", "AIzaSyKey222222222", status="Quota Exceeded", enabled=True)
    
    keys = db.get_gemini_keys()
    assert len(keys) == 2, f"Expected 2 keys, got {len(keys)}"
    print(f"Added keys count: {len(keys)}")
    print(f"Key 1: {keys[0]['name']} - Status: {keys[0]['status']}")
    print(f"Key 2: {keys[1]['name']} - Status: {keys[1]['status']}")
    
    db.update_gemini_key_stats(key_id1, status="Working", response_time_ms=145)
    keys_updated = db.get_gemini_keys()
    assert keys_updated[0]["response_time_ms"] == 145, "Latency stats update failed"
    print("[OK] Database key CRUD tests passed.")

    print("\n=== 3. Testing Gemini Provider Key Candidates & Rotation ===")
    provider = GeminiProvider(db=db)
    candidates = provider._get_key_candidates()
    print(f"Retrieved key candidates count: {len(candidates)}")
    assert len(candidates) == 2, "Candidate count mismatch"
    print("[OK] Gemini Provider key rotation candidates passed.")

    print("\n=== 4. Testing Local Models Detection ===")
    models = LocalModelManager.detect_all_models()
    print(f"Detected local models count: {len(models)}")
    for m in models:
        print(f" - Model: {m['name']} ({m['type']}) | Status: {m['status']} | Size: {m['size']}")
    assert len(models) > 0, "No local models returned"
    print("[OK] Local models detector tests passed.")

    # Cleanup test db
    del provider
    del db
    import gc
    gc.collect()
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
