# Windows Login Capture - Security Suite

A native Windows security solution that automatically captures webcam photos of unauthorized individuals attempting to unlock or log into your PC, logs forensic telemetry (Wi-Fi geolocation, IP address, timestamps), dispatches instant email alerts, and pops up a Security Center upon legit user unlock.

---

## 🚀 Quick Install (For End Users)

No Python or developer tools required.

1. Download **`WindowsLoginCapture_Setup_v1.0.exe`**.
2. Right-click the setup file and select **"Run as administrator"**.
3. Follow the installation wizard.
4. Once installed:
   * The background service starts automatically and runs 24/7.
   * The System Tray icon appears in your taskbar.
   * Lock your PC (`Win + L`) and test with an incorrect password.
   * When you log in with your correct password, the Security Center opens automatically displaying the intruder's photo and exact location!

---

## 🛠️ Architecture

* **Background Service (`WindowsLoginCaptureService.exe` / `phase2_service.py`):**
  Runs as `NT AUTHORITY\SYSTEM`. Monitors the Windows Security Event Log for failed logon events (`Event 4625`). Captures webcam photos, resolves high-precision Wi-Fi positioning (~100m accuracy) with reverse geocoding, and sends email alerts.
* **Unlock Trigger:**
  Detects Workstation Unlock (`Event 4801` / `Event 4624`) to trigger user-session review.
* **System Tray Companion (`WindowsLoginCaptureUI.exe --tray` / `tray_companion.py`):**
  Runs in the active user session. Monitors session unlock events (`WM_WTSSESSION_CHANGE`), displays native Windows balloon notifications, and brings the Security Center to the foreground.
* **Security Center UI (`app_ui.py` + `ui/`):**
  Modern Google Photos-inspired desktop interface powered by Microsoft Edge WebView2 (`pywebview`). Features photo lightbox viewer, automatic 2.5s polling, search filter, Google One storage gauge, and PIN-protected settings.
* **Single-Instance Enforcement:**
  Protected by a system-wide Win32 Named Mutex (`Global\WindowsLoginCapture_SingleInstance_UI_Mutex`) ensuring only one window ever exists.

---

## 💻 Building from Source

### Prerequisites
* Windows 10 or 11 (64-bit)
* Python 3.10+
* Inno Setup 6 (for installer packaging)

### Setup & Build Commands
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Compile standalone application bundle
python build_binaries.py

# 3. Compile the Inno Setup installer
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```
The final installer will be generated in `dist\WindowsLoginCapture_Setup_v1.0.exe`.
