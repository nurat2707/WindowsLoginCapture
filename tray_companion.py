"""
tray_companion.py
Windows Login Capture - Background System Tray & Post-Unlock Companion
Runs in the user's interactive desktop session (Session 1+).

Features:
- Windows native session unlock detection (WTS_SESSION_UNLOCK).
- Auto-pops up the Security Center dashboard if an unreviewed intruder photo was captured.
- Windows System Tray icon with status and context menu.
- Windows Startup (Registry Run key) management.
"""

import os
import sys
import time
import subprocess
import threading
import sqlite3
import winreg
import win32gui
import win32con
import win32ts
import win32api
import win32serviceutil

import paths
import app_ui

BASE_DIR = paths.BASE_DIR
DB_FILE = paths.DB_FILE

SERVICE_NAME = "WindowsLoginCapture"
APP_NAME = "WindowsLoginCaptureCompanion"
TRAY_TOOLTIP = "Windows Login Capture - Protection Active"

# Windows Session Change Constants (Win32 SDK)
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5

# Tray custom window message
WM_TRAYICON = win32con.WM_USER + 20
try:
    WM_TASKBARCREATED = win32gui.RegisterWindowMessage("TaskbarCreated")
except Exception:
    WM_TASKBARCREATED = 0


def force_foreground_window(hwnd):
    """Restores and forces window to foreground bypassing Windows foreground restrictions."""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        cur_thread = win32api.GetCurrentThreadId()
        fore_hwnd = win32gui.GetForegroundWindow()
        fore_thread, _ = win32process.GetWindowThreadProcessId(fore_hwnd)

        if cur_thread != fore_thread:
            win32process.AttachThreadInput(cur_thread, fore_thread, True)

        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)

        if cur_thread != fore_thread:
            win32process.AttachThreadInput(cur_thread, fore_thread, False)
    except Exception:
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass


def find_existing_ui_hwnd():
    """Finds existing Security Center HWND via EnumWindows (resilient to title changes)."""
    found = []
    def enum_cb(hwnd, extra):
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "Windows Login Capture - Security Center" in title:
                    found.append(hwnd)
        except Exception:
            pass
        return True
    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass
    return found[0] if found else None


def ensure_tray_running():
    """Starts the background tray companion process if not already running."""
    hwnd_tray = win32gui.FindWindow("WinLoginCaptureTrayClass", "WindowsLoginCaptureMessageWindow")
    if not hwnd_tray:
        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "--tray"], cwd=BASE_DIR)
            else:
                subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "tray_companion.py"), "--tray"], cwd=BASE_DIR)
        except Exception as e:
            print(f"[TRAY] Error starting companion: {e}")


class TrayCompanion:
    def __init__(self):
        self.hwnd = None
        self.hicon = None
        self.nid = None
        self.ui_process = None
        self.is_running = True

    @staticmethod
    def is_workstation_unlocked() -> bool:
        """Returns True if the current user session is unlocked and interactive."""
        import ctypes
        user32 = ctypes.windll.user32
        desk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
        if not desk:
            return False
        try:
            res = user32.SwitchDesktop(desk)
            return bool(res)
        finally:
            user32.CloseDesktop(desk)

    def run(self):
        # 1. Register Win32 Window Class for Tray and Session Notifications
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.lpszClassName = "WinLoginCaptureTrayClass"
        wc.lpfnWndProc = self.wnd_proc

        try:
            win32gui.RegisterClass(wc)
        except win32gui.error:
            pass  # Already registered

        # Create hidden top-level window (not visible, but discoverable by FindWindow)
        self.hwnd = win32gui.CreateWindowEx(
            0,
            wc.lpszClassName,
            "WindowsLoginCaptureMessageWindow",
            0,
            0, 0, 0, 0,
            0,
            0,
            wc.hInstance,
            None
        )

        # 2. Register for Windows Session Unlock/Logon events
        try:
            win32ts.WTSRegisterSessionNotification(self.hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
            print("[TRAY] Registered for Windows Session Unlock notifications.")
        except Exception as e:
            print(f"[TRAY WARNING] Could not register session notification: {e}")

        # 3. Create System Tray Icon
        self.create_tray_icon()

        # 4. Check on startup if there is an unreviewed breach waiting
        self.check_for_unreviewed_breach()

        # 5. Start background continuous breach monitor thread
        threading.Thread(target=self._breach_monitor_loop, daemon=True).start()

        # 6. Windows Message Pump
        print("[TRAY] Companion running in system tray. Right-click icon for options.")
        win32gui.PumpMessages()

    def _breach_monitor_loop(self):
        """Continuously checks every 1.5s if workstation is unlocked and an unreviewed breach exists."""
        while self.is_running:
            time.sleep(1.5)
            try:
                if self.is_workstation_unlocked():
                    hwnd_ui = win32gui.FindWindow(None, "Windows Login Capture - Security Center")
                    if not hwnd_ui:
                        self.check_for_unreviewed_breach()
            except Exception:
                pass

    def create_tray_icon(self):
        """Creates the shell notify icon in the Windows taskbar tray with retry."""
        try:
            # 32518 is IDI_SHIELD in WinUser.h
            self.hicon = win32gui.LoadIcon(0, 32518)
        except Exception:
            try:
                self.hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            except Exception:
                self.hicon = None

        if not self.hicon or not self.hwnd:
            return

        flags = win32gui.NIF_MESSAGE | win32gui.NIF_ICON | win32gui.NIF_TIP
        self.nid = (
            self.hwnd,
            0,
            flags,
            WM_TRAYICON,
            self.hicon,
            TRAY_TOOLTIP
        )

        def _try_add():
            for _ in range(15):
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, self.nid)
                    return
                except Exception:
                    time.sleep(1.0)

        threading.Thread(target=_try_add, daemon=True).start()

    def wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure to process Tray and Windows Session events."""
        if WM_TASKBARCREATED and msg == WM_TASKBARCREATED:
            self.create_tray_icon()
            return 0

        if msg == WM_WTSSESSION_CHANGE:
            # User unlocked the laptop screen or logged on
            if wparam in (WTS_SESSION_UNLOCK, WTS_SESSION_LOGON):
                print(f"[SESSION EVENT] Windows Screen Unlocked (wparam={wparam}). Checking for intruder alerts...")
                threading.Thread(target=self._delayed_unlock_check, daemon=True).start()

        elif msg == WM_TRAYICON:
            # Left Click or Double Click -> Open Security Center
            if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                self.open_security_center()
            # Right Click -> Show Context Menu
            elif lparam == win32con.WM_RBUTTONUP:
                self.show_context_menu()

        elif msg == win32con.WM_DESTROY:
            self.is_running = False
            self.cleanup()
            win32gui.PostQuitMessage(0)

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _delayed_unlock_check(self):
        """Polls with exponential/multiple retries right after screen unlock."""
        for delay in (0.3, 1.0, 2.0, 4.0):
            time.sleep(delay)
            if self.check_for_unreviewed_breach():
                break

    def check_for_unreviewed_breach(self) -> bool:
        """Queries SQLite for unreviewed intruder events. If found, pops up the UI. Returns True if handled."""
        if not os.path.exists(DB_FILE):
            return False

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            row = cursor.execute("""
                SELECT COUNT(*), MAX(id) FROM login_events 
                WHERE reviewed_by_user = 0
            """).fetchone()
            conn.close()

            unreviewed_count = row[0] if row else 0
            latest_id = row[1] if row else None

            if unreviewed_count > 0:
                # Debounce: if we already popped up the window for this exact breach, only bring to front
                if getattr(self, "_last_popped_id", None) == latest_id:
                    hwnd_ui = find_existing_ui_hwnd()
                    if hwnd_ui:
                        force_foreground_window(hwnd_ui)
                    return True

                self._last_popped_id = latest_id
                print(f"[ALERT] Found {unreviewed_count} unreviewed intruder event(s)! Popping up Security Center...")
                self.show_balloon_alert(unreviewed_count)
                self.open_security_center()
                return True
        except Exception as e:
            print(f"[TRAY ERROR] Failed to check breach status: {e}")
        return False

    def show_balloon_alert(self, count: int):
        """Displays native Windows balloon alert notification."""
        try:
            flags = win32gui.NIF_INFO | win32gui.NIF_ICON | win32gui.NIF_MESSAGE
            nid = (
                self.hwnd,
                0,
                flags,
                WM_TRAYICON,
                self.hicon,
                TRAY_TOOLTIP,
                f"Someone attempted an unauthorized login ({count} attempt{'s' if count > 1 else ''}). Click to review photo evidence.",
                2000,
                "🚨 Windows Security Alert: Intruder Detected",
                win32gui.NIIF_WARNING
            )
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, nid)
        except Exception:
            pass

    def open_security_center(self):
        """Launches or brings the Security Center UI to the foreground."""
        hwnd_ui = find_existing_ui_hwnd()
        if hwnd_ui:
            force_foreground_window(hwnd_ui)
            return

        # Check if another UI process is already starting or running via mutex
        try:
            import win32event, win32api, winerror
            test_mutex = win32event.CreateMutex(None, False, "Global\\WindowsLoginCapture_SingleInstance_UI_Mutex")
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                win32api.CloseHandle(test_mutex)
                for _ in range(15):
                    time.sleep(0.2)
                    hwnd = find_existing_ui_hwnd()
                    if hwnd:
                        force_foreground_window(hwnd)
                        return
                return
            win32api.CloseHandle(test_mutex)
        except Exception:
            pass

        # Otherwise launch GUI
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable], cwd=BASE_DIR)
        else:
            subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "app_ui.py")], cwd=BASE_DIR)

    def show_context_menu(self):
        """Renders right-click tray context menu."""
        menu = win32gui.CreatePopupMenu()

        # Check Service Status
        service_status = "Unknown"
        try:
            st = win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1]
            service_status = "Protected (Active)" if st == 4 else "Paused"
        except Exception:
            service_status = "Standalone Mode"

        win32gui.AppendMenu(menu, win32con.MF_STRING, 1001, "🛡️ Open Security Center")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING | win32con.MF_GRAYED, 1002, f"Service: {service_status}")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1003, "✕ Exit Companion")

        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        action = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
            pos[0],
            pos[1],
            0,
            self.hwnd,
            None
        )

        if action == 1001:
            self.open_security_center()
        elif action == 1003:
            self.cleanup()
            sys.exit(0)

    def cleanup(self):
        """Removes the tray icon and unregisters notifications on exit."""
        if self.nid:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self.nid)
            except Exception:
                pass
        try:
            win32ts.WTSUnRegisterSessionNotification(self.hwnd)
        except Exception:
            pass


# ================= AUTOSTART HELPERS =================
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def set_autostart(enable: bool = True):
    """Adds or removes the tray companion from Windows Startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if enable:
            if getattr(sys, "frozen", False):
                exe_or_script = f'"{sys.executable}" --tray'
            else:
                exe_or_script = f'"{sys.executable}" "{os.path.join(BASE_DIR, "tray_companion.py")}" --tray'
            winreg.SetValueEx(key, "WindowsLoginCapture", 0, winreg.REG_SZ, exe_or_script)
            print("[AUTOSTART] Windows Login Capture companion added to Windows Startup.")
        else:
            winreg.DeleteValue(key, "WindowsLoginCapture")
            print("[AUTOSTART] Removed from Windows Startup.")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[AUTOSTART ERROR] {e}")


if __name__ == "__main__":
    # If explicitly started in tray/startup background mode:
    if "--tray" in sys.argv or "--startup" in sys.argv:
        companion = TrayCompanion()
        companion.run()
        sys.exit(0)

    if "--enable-autostart" in sys.argv:
        set_autostart(True)
        sys.exit(0)
    elif "--disable-autostart" in sys.argv:
        set_autostart(False)
        sys.exit(0)

    # Windows Task Scheduler / Unlock trigger check
    if "--check-unlock" in sys.argv:
        has_unreviewed = False
        if os.path.exists(DB_FILE):
            try:
                conn = sqlite3.connect(DB_FILE)
                row = conn.execute("SELECT COUNT(*) FROM login_events WHERE reviewed_by_user = 0").fetchone()
                conn.close()
                if row and row[0] > 0:
                    has_unreviewed = True
            except Exception:
                pass

        if has_unreviewed:
            hwnd_ui = find_existing_ui_hwnd()
            if hwnd_ui:
                force_foreground_window(hwnd_ui)
            else:
                ensure_tray_running()
                app_ui.main()
            sys.exit(0)

        ensure_tray_running()
        sys.exit(0)

    # Standard execution (user clicked desktop/start shortcut or tray menu):
    # 1. If window already open, bring it to front
    hwnd_ui = find_existing_ui_hwnd()
    if hwnd_ui:
        force_foreground_window(hwnd_ui)
        sys.exit(0)

    # 2. Ensure tray companion is running in background if not already active
    ensure_tray_running()

    # 3. Open the Security Center UI
    app_ui.main()
