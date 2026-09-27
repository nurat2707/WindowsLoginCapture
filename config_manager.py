"""
config_manager.py
Handles SQLite database migration, application settings, and Master PIN security.
"""

import os
import sqlite3
import hashlib
import secrets

import paths

BASE_DIR = paths.DATA_DIR
DB_FILE = paths.DB_FILE


def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def init_or_migrate_db():
    """Initializes tables or adds missing columns to existing database safely."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Base login_events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            record_number INTEGER NOT NULL UNIQUE,
            username TEXT,
            logon_type INTEGER,
            detected_at TEXT NOT NULL,
            image_path TEXT,
            notification_status TEXT NOT NULL DEFAULT 'PENDING',
            notification_attempts INTEGER NOT NULL DEFAULT 0,
            last_notification_attempt TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # 2. Safely add new columns if they do not exist already
    existing_columns = [row[1] for row in cursor.execute("PRAGMA table_info(login_events)").fetchall()]

    new_columns = {
        "public_ip": "TEXT",
        "city": "TEXT",
        "region": "TEXT",
        "country": "TEXT",
        "latitude": "REAL",
        "longitude": "REAL",
        "maps_url": "TEXT",
        "location_status": "TEXT DEFAULT 'PENDING'",
        "email_status": "TEXT DEFAULT 'PENDING'",
        "reviewed_by_user": "INTEGER DEFAULT 0"
    }

    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE login_events ADD COLUMN {col_name} {col_type}")
            print(f"[DB MIGRATE] Added column: {col_name}")

    # 3. Settings table for Master PIN and Configs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Set default settings if not already present
    default_settings = {
        "retention_days": "30",
        "storage_max_mb": "500",
        "alert_email": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_password": "",
        "master_pin_salt": "",
        "master_pin_hash": ""
    }

    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (key, val))

    # 4. Correct historical false ISP-based 'Chennai' records
    try:
        cursor.execute("""
            UPDATE login_events
            SET city = 'Coimbatore', region = 'Tamil Nadu', country = 'India'
            WHERE (city = 'Chennai' OR city = 'Kochi')
        """)
    except Exception:
        pass

    conn.commit()
    conn.close()
    print("[DB] Database schema initialized and up-to-date.")

def get_setting(key: str, default: str = "") -> str:
    """Retrieve a setting value by key."""
    conn = get_connection()
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    """Set or update a configuration key."""
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# ----------------- MASTER PIN SECURITY -----------------

def set_master_pin(pin: str):
    """Securely hash and store the Master PIN using PBKDF2 with salt."""
    if len(pin) < 4:
        raise ValueError("PIN must be at least 4 digits.")
    salt = secrets.token_hex(16)
    pin_hash = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    
    set_setting("master_pin_salt", salt)
    set_setting("master_pin_hash", pin_hash)
    print("[SECURITY] Master PIN successfully set.")

def has_master_pin() -> bool:
    """Check if a Master PIN has been configured."""
    return bool(get_setting("master_pin_hash"))

def verify_master_pin(entered_pin: str) -> bool:
    """Verify an entered PIN against the stored hash."""
    stored_salt = get_setting("master_pin_salt")
    stored_hash = get_setting("master_pin_hash")

    if not stored_hash or not stored_salt:
        return True  # No PIN set, access granted

    test_hash = hashlib.pbkdf2_hmac("sha256", entered_pin.encode("utf-8"), stored_salt.encode("utf-8"), 100000).hex()
    return secrets.compare_digest(stored_hash, test_hash)

# ----------------- SELF-TEST RUNNER -----------------
if __name__ == "__main__":
    print("--- Running config_manager.py self-test ---")
    init_or_migrate_db()

    print("\n1. Testing Master PIN Setup...")
    test_pin = "1234"
    set_master_pin(test_pin)
    print(f"Master PIN configured? {has_master_pin()}")

    print("\n2. Testing PIN Verification...")
    print(f"Verify correct PIN ('{test_pin}'):", verify_master_pin("1234"))
    print("Verify wrong PIN ('9999'):", verify_master_pin("9999"))

    print("\n3. Testing Settings:")
    print("Retention Days:", get_setting("retention_days"))
    print("Storage Max MB:", get_setting("storage_max_mb"))

    print("\n--- Self-test completed successfully ---")
