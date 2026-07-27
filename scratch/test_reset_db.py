import sqlite3
import os

db_path = "project.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE settings SET value = '' WHERE key = 'last_video_path'")
    conn.commit()
    conn.close()
    print("Database last_video_path reset cleanly")
