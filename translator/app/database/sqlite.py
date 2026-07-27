import sqlite3
import os
import json
from typing import List, Optional, Dict, Any
from ..model.models import SubtitleItem, VoiceProfile, ProjectModel

class DatabaseManager:
    def __init__(self, db_path: str = "project.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Projects Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                video_path TEXT,
                audio_path TEXT,
                bgm_path TEXT,
                source_lang TEXT DEFAULT 'Chinese',
                target_lang TEXT DEFAULT 'Khmer',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Subtitles Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subtitles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                sub_index INTEGER,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                src_text TEXT,
                tgt_text TEXT,
                voice TEXT DEFAULT 'Male 1',
                status TEXT DEFAULT 'Pending',
                audio_path TEXT,
                character_name TEXT,
                confidence REAL DEFAULT 1.0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """)

            # Voices Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS voices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                gender TEXT NOT NULL,
                voice_id TEXT NOT NULL,
                engine TEXT DEFAULT 'Edge TTS',
                pitch REAL DEFAULT 1.0,
                speed REAL DEFAULT 1.0
            )
            """)

            # Translation Cache Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS translate_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_text TEXT UNIQUE NOT NULL,
                tgt_text TEXT NOT NULL,
                source_lang TEXT DEFAULT 'zh',
                target_lang TEXT DEFAULT 'km',
                provider TEXT DEFAULT 'Gemini',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            try:
                cursor.execute("""
                DELETE FROM translate_cache 
                WHERE tgt_text LIKE '%(%' 
                   OR tgt_text LIKE '%->%' 
                   OR tgt_text LIKE '%**%' 
                   OR tgt_text LIKE '%Gemini%'
                   OR tgt_text LIKE '%Error%'
                   OR tgt_text LIKE '%Master%'
                   OR tgt_text LIKE '%Iterative%'
                """)
            except Exception:
                pass

            # Settings Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)

            # Gemini API Keys Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS gemini_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_key_encrypted TEXT NOT NULL,
                status TEXT DEFAULT 'Working',
                enabled INTEGER DEFAULT 1,
                last_used DATETIME,
                requests_today INTEGER DEFAULT 0,
                total_requests INTEGER DEFAULT 0,
                response_time_ms INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            )
            """)

            # Migrate legacy gemini_api_key if present and gemini_api_keys table is empty
            cursor.execute("SELECT COUNT(*) FROM gemini_api_keys")
            if cursor.fetchone()[0] == 0:
                cursor.execute("SELECT value FROM settings WHERE key = 'gemini_api_key'")
                legacy_row = cursor.fetchone()
                if legacy_row and legacy_row["value"].strip():
                    from ..utils.crypto import encrypt_api_key
                    raw_k = legacy_row["value"].strip()
                    enc_k = encrypt_api_key(raw_k)
                    cursor.execute("""
                    INSERT INTO gemini_api_keys (name, api_key_encrypted, status, enabled, sort_order)
                    VALUES ('Default Key 1', ?, 'Working', 1, 1)
                    """, (enc_k,))

            # Default Voice Profiles
            cursor.execute("SELECT COUNT(*) FROM voices")
            if cursor.fetchone()[0] == 0:
                default_voices = [
                    ('Male 1', 'Male', 'km-KH-PisethNeural', 'Edge TTS', 1.0, 1.0),
                    ('Male 2', 'Male', 'km-KH-PisethNeural', 'Edge TTS', 0.9, 1.0),
                    ('Female 1', 'Female', 'km-KH-SreymomNeural', 'Edge TTS', 1.0, 1.0),
                    ('Female 2', 'Female', 'km-KH-SreymomNeural', 'Edge TTS', 1.1, 1.0),
                    ('Child', 'Child', 'km-KH-SreymomNeural', 'Edge TTS', 1.2, 1.15),
                    ('Old Man', 'Old Man', 'km-KH-PisethNeural', 'Edge TTS', 0.8, 0.9),
                    ('Old Woman', 'Old Woman', 'km-KH-SreymomNeural', 'Edge TTS', 0.85, 0.9)
                ]
                cursor.executemany("""
                INSERT INTO voices (name, gender, voice_id, engine, pitch, speed)
                VALUES (?, ?, ?, ?, ?, ?)
                """, default_voices)

            conn.commit()

    # Settings CRUD
    def get_setting(self, key: str, default: str = "") -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            conn.commit()

    # Gemini API Keys CRUD
    def get_gemini_keys(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM gemini_api_keys"
            if enabled_only:
                query += " WHERE enabled = 1"
            query += " ORDER BY sort_order ASC, id ASC"
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def add_gemini_key(self, name: str, raw_api_key: str, status: str = "Working", enabled: bool = True) -> int:
        from ..utils.crypto import encrypt_api_key
        enc_key = encrypt_api_key(raw_api_key.strip())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(sort_order) FROM gemini_api_keys")
            max_order = cursor.fetchone()[0] or 0
            cursor.execute("""
            INSERT INTO gemini_api_keys (name, api_key_encrypted, status, enabled, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """, (name.strip(), enc_key, status, 1 if enabled else 0, max_order + 1))
            conn.commit()
            return cursor.lastrowid

    def update_gemini_key(self, key_id: int, name: Optional[str] = None, raw_api_key: Optional[str] = None,
                           status: Optional[str] = None, enabled: Optional[bool] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name.strip())
            if raw_api_key is not None:
                from ..utils.crypto import encrypt_api_key
                updates.append("api_key_encrypted = ?")
                params.append(encrypt_api_key(raw_api_key.strip()))
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)

            if updates:
                params.append(key_id)
                cursor.execute(f"UPDATE gemini_api_keys SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()

    def update_gemini_key_stats(self, key_id: int, status: str, response_time_ms: int = 0):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE gemini_api_keys
            SET status = ?,
                response_time_ms = ?,
                last_used = CURRENT_TIMESTAMP,
                requests_today = requests_today + 1,
                total_requests = total_requests + 1
            WHERE id = ?
            """, (status, response_time_ms, key_id))
            conn.commit()

    def delete_gemini_key(self, key_id: int):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gemini_api_keys WHERE id = ?", (key_id,))
            conn.commit()

    def move_gemini_key(self, key_id: int, direction: str): # 'up' or 'down'
        keys = self.get_gemini_keys()
        for idx, k in enumerate(keys):
            if k["id"] == key_id:
                if direction == "up" and idx > 0:
                    other_idx = idx - 1
                elif direction == "down" and idx < len(keys) - 1:
                    other_idx = idx + 1
                else:
                    return
                # Swap sort_orders
                o_order = keys[other_idx]["sort_order"]
                c_order = k["sort_order"]
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE gemini_api_keys SET sort_order = ? WHERE id = ?", (o_order, k["id"]))
                    cursor.execute("UPDATE gemini_api_keys SET sort_order = ? WHERE id = ?", (c_order, keys[other_idx]["id"]))
                    conn.commit()
                break

    # Cache Operations
    def get_cached_translation(self, src_text: str, source_lang: str = "zh", target_lang: str = "km") -> Optional[str]:
        src_text_clean = src_text.strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT tgt_text FROM translate_cache
            WHERE src_text = ? AND source_lang = ? AND target_lang = ?
            """, (src_text_clean, source_lang, target_lang))
            row = cursor.fetchone()
            if row:
                tgt = row["tgt_text"]
                if tgt and not tgt.startswith("[Gemini") and not tgt.startswith("[Error") and not tgt.startswith("[Translate"):
                    return tgt
            return None

    def save_cached_translation(self, src_text: str, tgt_text: str, source_lang: str = "zh", target_lang: str = "km", provider: str = "Gemini"):
        src_text_clean = src_text.strip()
        tgt_text_clean = tgt_text.strip()
        if not src_text_clean or not tgt_text_clean or tgt_text_clean.startswith("[Gemini") or tgt_text_clean.startswith("[Error") or tgt_text_clean.startswith("[Translate"):
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO translate_cache (src_text, tgt_text, source_lang, target_lang, provider)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(src_text) DO UPDATE SET tgt_text = excluded.tgt_text, provider = excluded.provider
            """, (src_text_clean, tgt_text_clean, source_lang, target_lang, provider))
            conn.commit()

    # Subtitle Operations
    def save_subtitles(self, project_id: int, subtitles: List[SubtitleItem]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subtitles WHERE project_id = ?", (project_id,))
            sub_data = [
                (project_id, idx + 1, item.start_ms, item.end_ms, item.src_text, item.tgt_text,
                 item.voice, item.status, item.audio_path, item.character_name, item.confidence)
                for idx, item in enumerate(subtitles)
            ]
            cursor.executemany("""
            INSERT INTO subtitles (project_id, sub_index, start_ms, end_ms, src_text, tgt_text, voice, status, audio_path, character_name, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sub_data)
            conn.commit()

    def get_subtitles(self, project_id: int) -> List[SubtitleItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT sub_index, start_ms, end_ms, src_text, tgt_text, voice, status, audio_path, character_name, confidence
            FROM subtitles WHERE project_id = ? ORDER BY start_ms ASC
            """, (project_id,))
            rows = cursor.fetchall()
            return [
                SubtitleItem(
                    id=row["sub_index"],
                    start_ms=row["start_ms"],
                    end_ms=row["end_ms"],
                    src_text=row["src_text"] or "",
                    tgt_text=row["tgt_text"] or "",
                    voice=row["voice"] or "Male 1",
                    status=row["status"] or "Pending",
                    audio_path=row["audio_path"],
                    character_name=row["character_name"],
                    confidence=row["confidence"] or 1.0
                ) for row in rows
            ]

    # Voice Profiles
    def get_voice_profiles(self) -> List[VoiceProfile]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, gender, voice_id, engine, pitch, speed FROM voices")
            rows = cursor.fetchall()
            return [
                VoiceProfile(
                    id=row["id"],
                    name=row["name"],
                    gender=row["gender"],
                    voice_id=row["voice_id"],
                    engine=row["engine"],
                    pitch=row["pitch"],
                    speed=row["speed"]
                ) for row in rows
            ]
