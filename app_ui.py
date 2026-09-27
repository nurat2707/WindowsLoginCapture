"""
app_ui.py
Modern Google Photos-inspired desktop UI for Windows Login Capture.
Powered by Microsoft Edge WebView2 via pywebview.
Features: Chronological Photo Feed, Google Photos Lightbox Viewer,
Google One Storage Meter, PIN-Protected Settings, Windows Service Toggle,
and Real-Time Email Dispatch.
"""

import os
import sys
import base64
import ctypes
from datetime import datetime
import webview
import win32service
import win32serviceutil

# Set Per-Monitor V2 DPI awareness before creating any GUI window
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import config_manager
import storage_manager
import email_notifier

import paths

BASE_DIR = paths.BASE_DIR

SERVICE_NAME = "WindowsLoginCapture"

# Fast memory cache for base64 photo strings to keep UI buttery smooth
_img_b64_cache = {}

def get_cached_image_b64(path):
    if not path or not os.path.exists(path):
        return ""
    try:
        mtime = os.path.getmtime(path)
        if path in _img_b64_cache and _img_b64_cache[path][0] == mtime:
            return _img_b64_cache[path][1]
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        _img_b64_cache[path] = (mtime, encoded)
        return encoded
    except Exception:
        return ""

class AppApi:
    """Python API exposed to the JavaScript frontend via pywebview."""

    def get_incidents(self):
        """Fetch all login incidents with base64 encoded photos."""
        conn = config_manager.get_connection()
        rows = conn.execute("""
            SELECT id, record_number, username, detected_at, image_path,
                   public_ip, city, region, country, latitude, longitude,
                   maps_url, reviewed_by_user
            FROM login_events
            ORDER BY id DESC
        """).fetchall()
        conn.close()

        incidents = []
        for r in rows:
            rec_id, rec_num, user, det_at, img_path, ip, city, reg, country, lat, lon, maps, reviewed = r
            
            # Fast cached base64 image retrieval
            img_b64 = get_cached_image_b64(img_path)

            incidents.append({
                "id": rec_id,
                "record_number": rec_num,
                "username": user or "Standard Account",
                "detected_at": det_at,
                "image_path": img_path or "",
                "image_base64": img_b64,
                "public_ip": ip or "Offline / Unavailable",
                "city": city or "Unknown",
                "region": reg or "",
                "country": country or "",
                "latitude": lat or 0.0,
                "longitude": lon or 0.0,
                "maps_url": maps or "",
                "reviewed_by_user": bool(reviewed)
            })

        return incidents

    def verify_pin(self, pin: str) -> bool:
        """Verify entered Master PIN."""
        return config_manager.verify_master_pin(pin)

    def has_pin(self) -> bool:
        """Check if Master PIN is configured."""
        return config_manager.has_master_pin()

    def get_settings_bundle(self):
        """Bundle all configuration parameters and storage metrics."""
        return {
            "settings": {
                "retention_days": config_manager.get_setting("retention_days", "30"),
                "storage_max_mb": config_manager.get_setting("storage_max_mb", "500"),
                "alert_email": config_manager.get_setting("alert_email", ""),
                "smtp_user": config_manager.get_setting("smtp_user", ""),
                "smtp_password": config_manager.get_setting("smtp_password", "")
            },
            "storage": storage_manager.get_storage_stats()
        }

    def save_settings(self, data: dict):
        """Save settings and optionally update Master PIN."""
        try:
            if "retention_days" in data:
                config_manager.set_setting("retention_days", str(data["retention_days"]))
            if "storage_max_mb" in data:
                config_manager.set_setting("storage_max_mb", str(data["storage_max_mb"]))
            if "alert_email" in data:
                config_manager.set_setting("alert_email", str(data["alert_email"]))
            if "smtp_user" in data:
                config_manager.set_setting("smtp_user", str(data["smtp_user"]))
            if "smtp_password" in data:
                config_manager.set_setting("smtp_password", str(data["smtp_password"]))

            new_pin = data.get("new_pin", "").strip()
            if new_pin:
                if len(new_pin) < 4:
                    return {"success": False, "message": "Master PIN must be at least 4 digits."}
                config_manager.set_master_pin(new_pin)

            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def send_test_email(self, data: dict):
        """Send a test email alert with real photo attachment."""
        # Save temporary settings first
        if "alert_email" in data:
            config_manager.set_setting("alert_email", str(data["alert_email"]))
        if "smtp_user" in data:
            config_manager.set_setting("smtp_user", str(data["smtp_user"]))
        if "smtp_password" in data:
            config_manager.set_setting("smtp_password", str(data["smtp_password"]))

        # Retrieve latest incident from DB for realistic test data
        conn = config_manager.get_connection()
        latest = conn.execute("""
            SELECT detected_at, username, public_ip, city, maps_url, image_path 
            FROM login_events 
            ORDER BY id DESC LIMIT 1
        """).fetchone()
        conn.close()

        if latest:
            det_time, user, ip, city, maps, sample_img = latest
        else:
            det_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            user = "TestUser"
            ip = "103.5.112.80"
            city = "Coimbatore, Tamil Nadu"
            maps = "https://www.google.com/maps"
            sample_img = None

        success = email_notifier.send_alert_email(
            image_path=sample_img,
            username=user or "TestUser",
            detected_at=det_time,
            ip_address=ip or "103.5.112.80",
            city=city or "Coimbatore, Tamil Nadu",
            maps_url=maps or "https://www.google.com/maps",
            accuracy_m="92"
        )

        return {"success": success, "message": "Email sent" if success else "Failed to connect to SMTP server"}

    def purge_all(self, pin: str):
        """Wipe all incident history and photos with PIN authorization."""
        success = storage_manager.purge_all_records(pin)
        return {"success": success}

    def acknowledge_incident(self, incident_id: int):
        """Mark a single incident as reviewed."""
        conn = config_manager.get_connection()
        conn.execute("UPDATE login_events SET reviewed_by_user = 1 WHERE id = ?", (incident_id,))
        conn.commit()
        conn.close()
        return {"success": True}

    def acknowledge_all(self):
        """Mark all incidents as reviewed."""
        conn = config_manager.get_connection()
        conn.execute("UPDATE login_events SET reviewed_by_user = 1")
        conn.commit()
        conn.close()
        return {"success": True}

    def get_service_status(self):
        """Check status of WindowsLoginCapture background service."""
        try:
            status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1]
            if status == win32service.SERVICE_RUNNING:
                return {"status": "RUNNING"}
            elif status == win32service.SERVICE_STOPPED:
                return {"status": "STOPPED"}
            else:
                return {"status": "PENDING"}
        except Exception:
            return {"status": "STANDALONE"}

    def toggle_service(self, pin: str):
        """Start or Stop the Windows background service with PIN verification."""
        if not config_manager.verify_master_pin(pin):
            return {"success": False, "message": "Incorrect Master PIN."}

        current = self.get_service_status()["status"]
        if current not in ("RUNNING", "STOPPED"):
            return {
                "success": False,
                "message": "Windows Service is currently not installed. Running in standalone desktop mode."
            }

        action = "stop" if current == "RUNNING" else "start"

        # 1. Try direct Service Control Manager first
        try:
            if action == "stop":
                win32serviceutil.StopService(SERVICE_NAME)
                return {"success": True, "message": "Windows Service Protection Paused.", "status": "STOPPED"}
            else:
                win32serviceutil.StartService(SERVICE_NAME)
                return {"success": True, "message": "Windows Service Protection Started.", "status": "RUNNING"}
        except Exception as e:
            # 2. If non-admin (Access is denied error 5), request standard Windows UAC elevation
            err_str = str(e)
            if "Access is denied" in err_str or (hasattr(e, "winerror") and e.winerror == 5):
                try:
                    import ctypes
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        "net.exe",
                        f"{action} {SERVICE_NAME}",
                        None,
                        0  # SW_HIDE
                    )
                    if ret > 32:
                        import time
                        time.sleep(1.2)
                        new_status = self.get_service_status()["status"]
                        msg = "Protection Paused." if new_status == "STOPPED" else "Protection Active."
                        return {"success": True, "message": f"Windows Service {msg}", "status": new_status}
                    else:
                        return {"success": False, "message": "Administrator permission was declined."}
                except Exception as elev_err:
                    return {"success": False, "message": f"Elevation failed: {elev_err}"}

            return {"success": False, "message": f"Service control error: {err_str}"}

    def open_file_in_os(self, file_path: str):
        """Opens high-resolution photo in default Windows Photos viewer."""
        if file_path and os.path.exists(file_path):
            os.startfile(file_path)

    def toggle_maximize(self):
        """Toggle maximize / restore cleanly using Win32 API."""
        try:
            import win32gui
            import win32con
            hwnd = find_existing_ui_hwnd()
            if hwnd:
                import ctypes
                from ctypes import wintypes
                class WINDOWPLACEMENT(ctypes.Structure):
                    _fields_ = [
                        ('length', wintypes.UINT),
                        ('flags', wintypes.UINT),
                        ('showCmd', wintypes.UINT),
                        ('ptMinPosition', wintypes.POINT),
                        ('ptMaxPosition', wintypes.POINT),
                        ('rcNormalPosition', wintypes.RECT)
                    ]
                wp = WINDOWPLACEMENT()
                wp.length = ctypes.sizeof(WINDOWPLACEMENT)
                ctypes.windll.user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
                if wp.showCmd == win32con.SW_SHOWMAXIMIZED:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        except Exception:
            pass


UI_MUTEX_NAME = "Global\\WindowsLoginCapture_SingleInstance_UI_Mutex"
_ui_mutex = None

def find_existing_ui_hwnd():
    found = []
    def enum_cb(hwnd, extra):
        try:
            import win32gui
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "Windows Login Capture - Security Center" in title:
                    found.append(hwnd)
        except Exception:
            pass
        return True
    try:
        import win32gui
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass
    return found[0] if found else None

def bring_existing_ui_to_front():
    import time
    for _ in range(12):
        hwnd = find_existing_ui_hwnd()
        if hwnd:
            try:
                import tray_companion
                tray_companion.force_foreground_window(hwnd)
            except Exception:
                try:
                    import win32gui
                    import win32con
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.BringWindowToTop(hwnd)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            return True
        time.sleep(0.25)
    return False

def acquire_single_instance_mutex():
    global _ui_mutex
    try:
        import win32event
        import win32api
        import winerror
        _ui_mutex = win32event.CreateMutex(None, False, UI_MUTEX_NAME)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            bring_existing_ui_to_front()
            return False
    except Exception:
        pass
    return True


def main():
    # Enforce Single-Instance: Never allow 2 UI windows to open simultaneously!
    if not acquire_single_instance_mutex():
        print("[UI] Another Security Center window is already open. Brought to foreground.")
        return

    config_manager.init_or_migrate_db()

    html_path = paths.HTML_INDEX

    api = AppApi()
    window = webview.create_window(
        title="Windows Login Capture - Security Center",
        url=html_path,
        js_api=api,
        width=1080,
        height=720,
        min_size=(400, 300),
        background_color="#0e1117"
    )

    webview.start(debug=False)

if __name__ == "__main__":
    main()
