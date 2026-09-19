import sqlite3

db = r"F:\WindowsLoginCapture\login_events.db"

conn = sqlite3.connect(db)

rows = conn.execute("""
    SELECT
        id,
        event_id,
        record_number,
        username,
        logon_type,
        detected_at,
        image_path,
        notification_status
    FROM login_events
    ORDER BY id DESC
""").fetchall()

for row in rows:
    print(row)

conn.close()
