import traceback
import os
import time
import sqlite3
from datetime import datetime

import cv2

import win32evtlog
import win32event
import win32service
import win32serviceutil
import servicemanager
import win32api

SERVICE_NAME = "WindowsLoginCapture"
DISPLAY_NAME = "Windows Login Capture Service"
DESCRIPTION = "Monitors Windows Security log for failed login attempts."

LOG_FILE = r"F:\WindowsLoginCapture\failed_logins.txt"
OUTPUT_DIR = r"F:\WindowsLoginCapture"
ERROR_LOG = r"F:\WindowsLoginCapture\service_error.txt"
DB_FILE = r"F:\WindowsLoginCapture\login_events.db"

# Tightened from 1000ms. This call is cheap (two small syscalls +
# a possible ReadEventLog only when count changed), so a much
# shorter interval doesn't meaningfully load the CPU.
POLL_INTERVAL_MS = 200


class FailedLoginService(win32serviceutil.ServiceFramework):

    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = DISPLAY_NAME
    _svc_description_ = DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.security_log = None
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(DB_FILE)

        conn.execute("""
                CREATE TABLE IF NOT EXISTS login_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    record_number INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    detected_at TEXT NOT NULL,
                    image_path TEXT,
                    notification_status TEXT NOT NULL DEFAULT 'PENDING',
                    notification_attempts INTEGER NOT NULL DEFAULT 0,
                    last_notification_attempt TEXT,
                    created_at TEXT NOT NULL
                )
            """)

        conn.commit()
        conn.close()

        servicemanager.LogInfoMsg("SQLite database initialized.")

    def save_event(self, event_id, record_number, username, detected_at, image_path):
        conn = sqlite3.connect(DB_FILE)

        conn.execute(
            """
        INSERT INTO login_events (
        event_id,
        record_number,
        username,
        detected_at,
        image_path,
        notification_status,
        created_at
    )
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
    """,
            (
                event_id,
                record_number,
                username,
                detected_at.isoformat(),
                image_path,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        conn.close()

        servicemanager.LogInfoMsg(f"EVENT STORED | Record={record_number}")

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Windows Login Capture Service started.")
        try:
            self.run_monitor()
        except Exception:
            error = traceback.format_exc()
            servicemanager.LogErrorMsg("SERVICE ERROR:\n" + error)
            try:
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 60 + "\nSERVICE ERROR\n" + error)
            except Exception:
                pass
            raise
        finally:
            self.cleanup()

    # ==================================================
    # CAMERA - cold-start per event (LED only lights
    # up during the capture window, as intended)
    # ==================================================

    def capture_photo(self):
        servicemanager.LogInfoMsg("Attempting webcam capture...")
        camera = None
        t0 = time.time()

        try:
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

            if not camera.isOpened():
                servicemanager.LogErrorMsg("FAILED: Could not open webcam.")
                return

            t_open = time.time()

            for _ in range(4):
                camera.read()

            t_warm = time.time()

            ret, frame = camera.read()
            if not ret:
                servicemanager.LogErrorMsg("FAILED: Could not capture webcam frame.")
                return

            t_read = time.time()

            filename = os.path.join(
                OUTPUT_DIR,
                "failed_login_"
                + datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                + ".jpg",
            )
            success = cv2.imwrite(filename, frame)
            t_save = time.time()

            servicemanager.LogInfoMsg(
                f"TOTAL CAPTURE TIME: {int((t_save - t0) * 1000)} ms "
                f"(open {int((t_open - t0) * 1000)} / warmup {int((t_warm - t_open) * 1000)} "
                f"/ read {int((t_read - t_warm) * 1000)} / save {int((t_save - t_read) * 1000)})"
            )

            if success:
                servicemanager.LogInfoMsg("PHOTO CAPTURED: " + filename)
                return filename
            else:
                servicemanager.LogErrorMsg("FAILED: Could not save photo.")
                return None

        except Exception:
            error = traceback.format_exc()
            servicemanager.LogErrorMsg("CAMERA ERROR:\n" + error)
            try:
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 60 + "\nCAMERA ERROR\n" + error)
            except Exception:
                pass
        finally:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass

    # ==================================================
    # SECURITY LOG MONITOR - plain polling, proven reliable
    # ==================================================

    def run_monitor(self):
        servicemanager.LogInfoMsg("Opening Security log...")
        self.security_log = win32evtlog.OpenEventLog(None, "Security")
        servicemanager.LogInfoMsg("Security log opened.")

        oldest = win32evtlog.GetOldestEventLogRecord(self.security_log)
        count = win32evtlog.GetNumberOfEventLogRecords(self.security_log)
        last_record = (oldest + count - 1) if count > 0 else oldest

        servicemanager.LogInfoMsg("Starting from Security record: " + str(last_record))

        while True:
            if (
                win32event.WaitForSingleObject(self.stop_event, 0)
                == win32event.WAIT_OBJECT_0
            ):
                servicemanager.LogInfoMsg("Service stopping.")
                break

            last_record = self.read_new_events(last_record)

            if (
                win32event.WaitForSingleObject(self.stop_event, POLL_INTERVAL_MS)
                == win32event.WAIT_OBJECT_0
            ):
                servicemanager.LogInfoMsg("Service stopping.")
                break

    def read_new_events(self, last_record):
        try:
            oldest = win32evtlog.GetOldestEventLogRecord(self.security_log)
            count = win32evtlog.GetNumberOfEventLogRecords(self.security_log)

            if count == 0:
                return last_record

            newest = oldest + count - 1
            if newest <= last_record:
                return last_record

            first_record = last_record + 1

            events = win32evtlog.ReadEventLog(
                self.security_log,
                win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEEK_READ,
                first_record,
            )

            newest_processed = last_record

            for event in events:
                record_id = event.RecordNumber
                if record_id <= last_record:
                    continue
                if record_id > newest_processed:
                    newest_processed = record_id

                event_id = event.EventID & 0xFFFF
                username = (
                    event.StringInserts[5]
                    if event.StringInserts and len(event.StringInserts) > 5
                    else None
                )

                if event_id == 4625:
                    t_detect = datetime.now()

                    servicemanager.LogInfoMsg(f"FAILED LOGIN USERNAME: {username}")
                    servicemanager.LogInfoMsg(
                        f"FAILED LOGIN DETECTED | Record={record_id} | Detected={t_detect.isoformat()}"
                    )
                    try:
                        with open(LOG_FILE, "a", encoding="utf-8") as f:
                            f.write(
                                f"FAILED LOGIN | Record={record_id} | {t_detect.isoformat()}\n"
                            )
                    except Exception:
                        servicemanager.LogErrorMsg(
                            "LOG WRITE ERROR:\n" + traceback.format_exc()
                        )

                    image_path = self.capture_photo()

                    self.save_event(
                        event_id=event_id,
                        record_number=record_id,
                        username=username,
                        detected_at=t_detect,
                        image_path=image_path,
                    )

            return newest_processed

        except Exception:
            error = traceback.format_exc()
            servicemanager.LogErrorMsg("Error reading Security events:\n" + error)
            try:
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write("\n" + "=" * 60 + "\nREAD EVENT ERROR\n" + error)
            except Exception:
                pass
            return last_record

    def cleanup(self):
        if self.security_log:
            try:
                win32evtlog.CloseEventLog(self.security_log)
            except Exception:
                pass
            self.security_log = None
        if self.stop_event:
            try:
                win32api.CloseHandle(self.stop_event)
            except Exception:
                pass
            self.stop_event = None


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(FailedLoginService)
