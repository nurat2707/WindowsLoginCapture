import os
import sys
import sqlite3
import time
import threading
import traceback
from datetime import datetime

import cv2
import servicemanager
import win32api
import win32event
import win32evtlog
import win32service
import win32serviceutil

import config_manager
import geo_tracker
import email_notifier
import storage_manager

SERVICE_NAME = "WindowsLoginCapture"
DISPLAY_NAME = "Windows Login Capture Service"
DESCRIPTION = "Monitors Windows Security log for failed login attempts, captures webcam photos, and dispatches security alerts."

import paths

LOG_FILE = paths.LOG_FILE
OUTPUT_DIR = paths.PHOTOS_DIR
ERROR_LOG = os.path.join(paths.DATA_DIR, "service_error.txt")
DB_FILE = paths.DB_FILE


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
        try:
            config_manager.init_or_migrate_db()
            servicemanager.LogInfoMsg("SQLite database schema initialized and up-to-date.")
        except Exception:
            servicemanager.LogErrorMsg("Error initializing database:\n" + traceback.format_exc())

    def check_trigger_unlock_popup(self):
        """Checks if any unreviewed breach exists and triggers UI popup via Task Scheduler."""
        try:
            conn = config_manager.get_connection()
            row = conn.execute("SELECT COUNT(*) FROM login_events WHERE reviewed_by_user = 0").fetchone()
            conn.close()
            unreviewed = row[0] if row else 0
            if unreviewed > 0:
                servicemanager.LogInfoMsg(f"UNLOCK DETECTED with {unreviewed} unreviewed breach(es)! Triggering unlock popup...")
                import subprocess
                subprocess.run(
                    ["schtasks.exe", "/run", "/tn", "WindowsLoginCaptureUnlockCheck"],
                    capture_output=True,
                    timeout=5
                )
        except Exception:
            pass

    def handle_incident(self, event_id, record_id, username, logon_type, detected_at, image_path):
        """Processes geolocation, updates record in DB, dispatches email, and enforces retention."""
        try:
            # 1. High-accuracy Wi-Fi / IP Geolocation (runs in background)
            loc = geo_tracker.get_location_details()

            # 2. Update record in database with resolved location
            conn = config_manager.get_connection()
            conn.execute(
                """
                UPDATE login_events SET
                    public_ip = ?,
                    city = ?,
                    region = ?,
                    country = ?,
                    latitude = ?,
                    longitude = ?,
                    maps_url = ?,
                    location_status = ?
                WHERE record_number = ?
                """,
                (
                    loc.get("public_ip"),
                    loc.get("city"),
                    loc.get("region"),
                    loc.get("country"),
                    loc.get("latitude"),
                    loc.get("longitude"),
                    loc.get("maps_url"),
                    loc.get("location_status"),
                    record_id,
                ),
            )
            conn.commit()
            conn.close()

            servicemanager.LogInfoMsg(
                f"INCIDENT GEO-UPDATED | Record={record_id} | User={username} | Loc={loc.get('city')}"
            )

            # 3. Real-Time Alert Email Dispatch
            det_formatted = detected_at.strftime("%Y-%m-%d %I:%M:%S %p")
            acc_str = str(loc.get("accuracy_m", ""))
            city_str = f"{loc.get('city', 'Unknown')}, {loc.get('region', '')}, {loc.get('country', '')}".strip(", ")

            sent = email_notifier.send_alert_email(
                image_path=image_path,
                username=username or "Standard Account",
                detected_at=det_formatted,
                ip_address=loc.get("public_ip", "Offline"),
                city=city_str,
                maps_url=loc.get("maps_url", ""),
                accuracy_m=acc_str
            )

            if sent:
                conn = config_manager.get_connection()
                conn.execute("UPDATE login_events SET email_status = 'SENT' WHERE record_number = ?", (record_id,))
                conn.commit()
                conn.close()

            # 4. Enforce storage quotas & 30-day retention
            storage_manager.enforce_retention_policy()

        except Exception:
            err = traceback.format_exc()
            servicemanager.LogErrorMsg("INCIDENT HANDLER ERROR:\n" + err)
            self.write_error_log("INCIDENT HANDLER ERROR", err)

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
            self.write_error_log("SERVICE ERROR", error)
            raise
        finally:
            self.cleanup()

    def capture_photo(self):
        servicemanager.LogInfoMsg("Attempting webcam capture...")
        camera = None
        start_time = time.time()

        try:
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

            if not camera.isOpened():
                servicemanager.LogErrorMsg("FAILED: Could not open webcam.")
                return None

            open_time = time.time()

            for _ in range(4):
                camera.read()

            warmup_time = time.time()
            ret, frame = camera.read()

            if not ret:
                servicemanager.LogErrorMsg("FAILED: Could not capture webcam frame.")
                return None

            read_time = time.time()

            filename = os.path.join(
                OUTPUT_DIR,
                "failed_login_"
                + datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                + ".jpg",
            )

            success = cv2.imwrite(filename, frame)
            save_time = time.time()

            servicemanager.LogInfoMsg(
                f"TOTAL CAPTURE TIME: {int((save_time - start_time) * 1000)} ms"
            )

            if success:
                servicemanager.LogInfoMsg("PHOTO CAPTURED: " + filename)
                return filename

            servicemanager.LogErrorMsg("FAILED: Could not save photo.")
            return None

        except Exception:
            error = traceback.format_exc()
            servicemanager.LogErrorMsg("CAMERA ERROR:\n" + error)
            self.write_error_log("CAMERA ERROR", error)
            return None

        finally:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass

    def run_monitor(self):
        servicemanager.LogInfoMsg("Opening Security log...")
        self.security_log = win32evtlog.OpenEventLog(None, "Security")
        servicemanager.LogInfoMsg("Security log opened.")

        oldest = win32evtlog.GetOldestEventLogRecord(self.security_log)
        count = win32evtlog.GetNumberOfEventLogRecords(self.security_log)
        last_record = oldest + count - 1 if count > 0 else oldest

        servicemanager.LogInfoMsg(f"Starting from Security record: {last_record}")

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
                (win32evtlog.EVENTLOG_FORWARDS_READ | win32evtlog.EVENTLOG_SEEK_READ),
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

                # WORKSTATION UNLOCK / LOGON DETECTION:
                # Event 4801: Workstation Unlocked
                # Event 4624: Successful Logon (Type 2=Interactive, 7=Unlock, 11=CachedUnlock)
                if event_id in (4801, 4624):
                    logon_type = None
                    if event_id == 4624 and event.StringInserts and len(event.StringInserts) > 8:
                        try:
                            logon_type = int(event.StringInserts[8])
                        except (ValueError, TypeError):
                            pass
                    if event_id == 4801 or logon_type in (2, 7, 10, 11):
                        self.check_trigger_unlock_popup()
                    continue

                if event_id != 4625:
                    continue

                username = (
                    event.StringInserts[5]
                    if event.StringInserts and len(event.StringInserts) > 5
                    else None
                )

                logon_type = None
                if event.StringInserts and len(event.StringInserts) > 10:
                    try:
                        logon_type = int(event.StringInserts[10])
                    except (ValueError, TypeError):
                        pass

                # STRICT FILTER: Only capture physical keyboard attempts at lock/logon screen
                # LogonType 2 = Interactive (Console physical logon)
                # LogonType 11 = CachedInteractive (Workstation unlock screen)
                # LogonType 10 = RemoteInteractive (Remote Desktop)
                if logon_type not in (2, 10, 11):
                    continue

                logon_process = (
                    event.StringInserts[11].strip()
                    if event.StringInserts and len(event.StringInserts) > 11
                    else ""
                )
                process_name = (
                    event.StringInserts[18].lower()
                    if event.StringInserts and len(event.StringInserts) > 18
                    else ""
                )

                # Must originate from the Windows Logon/Lock Screen UI
                is_lock_screen = (
                    logon_process in ("User32", "seclogo", "winlogon", "CredPro")
                    or process_name.endswith(("logonui.exe", "winlogon.exe"))
                    or (not process_name and logon_process in ("User32", "seclogo"))
                )
                if not is_lock_screen:
                    continue

                detected_at = datetime.now()

                servicemanager.LogInfoMsg(
                    f"FAILED LOGIN | Record={record_id} | Username={username} | LogonType={logon_type}"
                )

                try:
                    with open(LOG_FILE, "a", encoding="utf-8") as f:
                        f.write(
                            f"FAILED LOGIN | Record={record_id} | Username={username} | LogonType={logon_type} | {detected_at.isoformat()}\n"
                        )
                except Exception:
                    pass

                image_path = self.capture_photo()

                # IMMEDIATELY write incident to SQLite (<5ms) so unlock detection finds it instantly!
                try:
                    conn = config_manager.get_connection()
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO login_events (
                            event_id,
                            record_number,
                            username,
                            logon_type,
                            detected_at,
                            image_path,
                            public_ip,
                            city,
                            region,
                            country,
                            latitude,
                            longitude,
                            maps_url,
                            location_status,
                            email_status,
                            reviewed_by_user,
                            created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'Resolving...', 'Resolving...', '', '', 0.0, 0.0, '', 'PENDING', 'PENDING', 0, ?)
                        """,
                        (
                            event_id,
                            record_id,
                            username,
                            logon_type,
                            detected_at.strftime("%Y-%m-%d %H:%M:%S"),
                            image_path,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    servicemanager.LogInfoMsg(f"INCIDENT SAVED TO SQLITE | Record={record_id} | User={username}")
                except Exception as db_err:
                    servicemanager.LogErrorMsg(f"Immediate DB save error: {db_err}")

                # Process location, database, email, and storage in a background thread
                threading.Thread(
                    target=self.handle_incident,
                    args=(event_id, record_id, username, logon_type, detected_at, image_path),
                    daemon=True,
                ).start()

            return newest_processed

        except Exception:
            error = traceback.format_exc()
            servicemanager.LogErrorMsg("Error reading Security events:\n" + error)
            self.write_error_log("READ EVENT ERROR", error)
            return last_record

    def write_error_log(self, error_type, error):
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 60 + f"\n{error_type}\n" + error)
        except Exception:
            pass

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
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FailedLoginService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FailedLoginService)
