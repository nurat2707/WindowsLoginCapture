"""
storage_manager.py
Enforces storage quotas, age-based expiration (30 days), and FIFO rotation
for captured intruder photos and database logs.
"""

import os
import sqlite3
from datetime import datetime, timedelta
import config_manager

BASE_DIR = r"F:\WindowsLoginCapture"
DB_FILE = os.path.join(BASE_DIR, "login_events.db")

def get_storage_stats() -> dict:
    """Calculates total disk usage of saved intruder photos."""
    max_mb = float(config_manager.get_setting("storage_max_mb", "500"))
    retention_days = int(config_manager.get_setting("retention_days", "30"))

    total_bytes = 0
    photo_count = 0

    if os.path.exists(BASE_DIR):
        for fname in os.listdir(BASE_DIR):
            if fname.lower().endswith((".jpg", ".jpeg", ".png")) and fname.startswith("failed_login_"):
                fpath = os.path.join(BASE_DIR, fname)
                if os.path.isfile(fpath):
                    total_bytes += os.path.getsize(fpath)
                    photo_count += 1

    used_mb = round(total_bytes / (1024 * 1024), 2)
    percent_used = round((used_mb / max_mb) * 100, 1) if max_mb > 0 else 0.0

    return {
        "used_mb": used_mb,
        "max_mb": max_mb,
        "percent_used": percent_used,
        "photo_count": photo_count,
        "retention_days": retention_days
    }

def enforce_retention_policy() -> dict:
    """
    Purges records older than retention_days, and performs FIFO rotation
    if folder size exceeds max_mb quota.
    """
    stats = get_storage_stats()
    retention_days = stats["retention_days"]
    max_mb = stats["max_mb"]

    conn = config_manager.get_connection()
    cursor = conn.cursor()

    deleted_by_age = 0
    deleted_by_size = 0

    # 1. Purge records older than retention_days
    cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
    old_records = cursor.execute(
        "SELECT id, image_path FROM login_events WHERE detected_at < ?", (cutoff_date,)
    ).fetchall()

    for record_id, image_path in old_records:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass
        cursor.execute("DELETE FROM login_events WHERE id = ?", (record_id,))
        deleted_by_age += 1

    conn.commit()

    # 2. FIFO Size Cap Rotation (if still exceeding quota)
    current_stats = get_storage_stats()
    if current_stats["used_mb"] > max_mb:
        records = cursor.execute(
            "SELECT id, image_path FROM login_events WHERE image_path IS NOT NULL ORDER BY id ASC"
        ).fetchall()

        for record_id, image_path in records:
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception:
                    pass
            cursor.execute("UPDATE login_events SET image_path = NULL WHERE id = ?", (record_id,))
            deleted_by_size += 1

            if get_storage_stats()["used_mb"] <= (max_mb * 0.8):
                break

        conn.commit()

    conn.close()

    return {
        "deleted_by_age": deleted_by_age,
        "deleted_by_size": deleted_by_size,
        "current_stats": get_storage_stats()
    }

def purge_all_records(entered_pin: str) -> bool:
    """
    PIN-protected emergency purge of all incident photos and database entries.
    """
    if not config_manager.verify_master_pin(entered_pin):
        print("[STORAGE] Authorization failed: Invalid Master PIN.")
        return False

    conn = config_manager.get_connection()
    cursor = conn.cursor()

    records = cursor.execute("SELECT image_path FROM login_events WHERE image_path IS NOT NULL").fetchall()
    for (img_path,) in records:
        if img_path and os.path.exists(img_path):
            try:
                os.remove(img_path)
            except Exception:
                pass

    cursor.execute("DELETE FROM login_events")
    conn.commit()
    conn.close()

    print("[STORAGE] All incident history and photos successfully purged.")
    return True

# ----------------- SELF-TEST RUNNER -----------------
if __name__ == "__main__":
    print("--- Running storage_manager.py self-test ---")
    
    stats = get_storage_stats()
    print("\n1. Current Storage Usage:")
    print(f"Photos Count : {stats['photo_count']}")
    print(f"Space Used   : {stats['used_mb']} MB / {stats['max_mb']} MB ({stats['percent_used']}%)")
    print(f"Retention Cap: {stats['retention_days']} days")

    print("\n2. Testing Retention & FIFO Enforcement...")
    result = enforce_retention_policy()
    print(f"Deleted by age (> {stats['retention_days']} days) : {result['deleted_by_age']}")
    print(f"Deleted by size limit        : {result['deleted_by_size']}")

    print("\n3. Testing PIN-Protected Purge Security:")
    print("Attempting purge with WRONG PIN ('0000'):")
    print("Result:", purge_all_records("0000"))

    print("\n--- Self-test completed successfully ---")
