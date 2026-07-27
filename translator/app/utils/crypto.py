import base64
import os

_SECRET_SALT = b"dubify_ai_secure_salt_2026"

def encrypt_api_key(plain_key: str) -> str:
    """Encrypt/obfuscate API key before saving to SQLite database."""
    if not plain_key:
        return ""
    # Check if already encrypted marker
    if plain_key.startswith("enc:v1:"):
        return plain_key
    
    # Simple XOR + Base64 encoding with secret salt
    raw_bytes = plain_key.encode('utf-8')
    encrypted_bytes = bytearray()
    for i, b in enumerate(raw_bytes):
        encrypted_bytes.append(b ^ _SECRET_SALT[i % len(_SECRET_SALT)])
    
    encoded = base64.b64encode(encrypted_bytes).decode('ascii')
    return f"enc:v1:{encoded}"

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt stored API key from SQLite database."""
    if not encrypted_key:
        return ""
    if not encrypted_key.startswith("enc:v1:"):
        return encrypted_key  # Fallback for plain unencrypted key legacy support
    
    try:
        encoded = encrypted_key[7:]
        encrypted_bytes = base64.b64decode(encoded.encode('ascii'))
        raw_bytes = bytearray()
        for i, b in enumerate(encrypted_bytes):
            raw_bytes.append(b ^ _SECRET_SALT[i % len(_SECRET_SALT)])
        return raw_bytes.decode('utf-8')
    except Exception:
        return encrypted_key

def mask_api_key(api_key: str) -> str:
    """Mask API key for safe UI display (e.g., AIzaSy...x89A)."""
    if not api_key:
        return ""
    if api_key.startswith("enc:v1:"):
        api_key = decrypt_api_key(api_key)
    
    if len(api_key) <= 8:
        return "********"
    return f"{api_key[:6]}...{api_key[-4:]}"
