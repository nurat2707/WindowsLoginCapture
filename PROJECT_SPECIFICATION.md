# Windows Login Capture (Intruder Detection System)
## System Architecture, Feature Roadmap & Implementation Blueprint

---

## 1. Executive Summary & Vision

**Windows Login Capture** is a lightweight, stealthy, and robust security system for Windows laptops and desktops. Whenever an unauthorized individual attempts to guess or enter an incorrect Windows password or PIN, the system instantly:
1. Detects the failed login security event (`Event ID 4625`) in real-time.
2. Silently triggers the webcam to capture high-quality photos of the intruder.
3. Gathers real-time telemetry (exact timestamp, target account, logon type, IP address, and geographic location).
4. Dispatches an immediate security alert email with photo evidence attached.
5. Displays a rich, alert screen to the legitimate owner upon their next successful login.
6. Manages storage footprint automatically through configurable retention and rotation policies.
7. Packages into a standalone, single-click Windows executable (`.exe` installer) for zero-dependency consumer distribution.

---

## 2. Current State Assessment (Phase 2 Baseline)

The current implementation in `phase2_service.py` establishes the foundational core:
- **Windows Service Architecture:** Implemented via `pywin32` (`win32serviceutil.ServiceFramework`).
- **Security Event Polling:** Monitors Windows Security log for `Event ID 4625` (Failed Logon) with forward-seeking pointer tracking.
- **Webcam Capture:** OpenCV (`cv2.VideoCapture(0, cv2.CAP_DSHOW)`) with camera warmup frames.
- **Local Storage:** SQLite database (`login_events.db`) and text log (`failed_logins.txt`) recording failed attempts.
- **Current Limitations to Overcome:**
  - Hardcoded paths (`F:\WindowsLoginCapture`). Must use dynamic Windows standard paths (e.g., `%ProgramData%` and `%AppData%`).
  - Windows Services run in **Session 0** (non-interactive). They cannot directly display UI popups on the user's interactive desktop (Session 1+).
  - No internet / network / geolocation integration.
  - No email dispatch or alert triggers.
  - Unbounded photo storage accumulation.
  - Requires manual Python environment setup and service command-line registration.

---

## 3. Core Requirements & Detailed Implementation Plan

### 3.1. Standalone Distribution (.exe & Installer)

#### Goal
Allow any non-technical user to download a single setup file, install it with one click, and have it immediately active and self-protecting across reboots.

#### Implementation Architecture
- **Packaging Engine:** **PyInstaller** or **Nuitka** to compile the Python source code, OpenCV binaries, and pywin32 C-extensions into standalone executables without requiring Python on the target machine.
- **Installer Builder:** **Inno Setup** (or **WiX Toolset**) to generate a production-ready Windows installer (`WindowsLoginCapture_Setup.exe`):
  - Automatically provisions directory structures in `%ProgramData%\WindowsLoginCapture` (for service data/db) and `%ProgramFiles%\WindowsLoginCapture` (for binaries).
  - Automatically verifies and enables the Windows Security Audit Policy for logon events:
    ```cmd
    auditpol /set /subcategory:"Logon" /failure:enable /success:enable
    ```
    *(Essential: without this policy enabled in Windows, Event 4625 will never be generated!)*
  - Installs and starts the background Windows Service or Task Scheduler daemon with highest administrative privileges.
  - Adds the User Tray/Notification Companion to the Windows Startup registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).
  - Creates desktop/start-menu shortcuts and uninstaller hooks.

---

### 3.2. Real-Time Geolocation Tracking

#### Goal
Record the physical and network location of the device at the moment a breach attempt is detected.

#### Implementation Architecture
- **Dual-Tier Geolocation Strategy:**
  1. **Primary (Fast IP Geolocation):**
     - Queries fast, lightweight JSON APIs (such as `ipinfo.io`, `ip-api.com`, or `freegeoip.app`).
     - Extracts: Public IP, City, Region, Country, Latitude/Longitude coordinates, ISP/Organization, and Postal Code.
     - Generates a clickable Google Maps URL: `https://www.google.com/maps?q={lat},{lon}`.
  2. **Secondary (Windows Location API - Native GPS/Wi-Fi Triangulation):**
     - Uses Windows Native Geolocation (`winsdk` / `winrt.windows.devices.geolocation` or PowerShell `.NET` interop) to obtain high-precision coordinates using nearby Wi-Fi BSSID signals even if IP geolocation is coarse.
- **Offline & Network Reconnect Queuing:**
  - If the laptop is disconnected from Wi-Fi when the intruder enters a wrong password, location coordinates are marked as `OFFLINE_PENDING`.
  - As soon as the laptop connects to any network (monitored via `win32con.WM_DEVICECHANGE` or network availability hooks), the service automatically resolves and enriches the pending event record with the location data.

---

### 3.3. Legitimate User Post-Unlock UI Alert & Dashboard

#### Goal
When the laptop owner successfully unlocks or logs into their machine after an intrusion attempt, an attention-grabbing, clean dashboard automatically appears, presenting evidence of the breach.

#### Implementation Architecture (Session 0 vs Session 1 Separation)
Because Windows blocks Services (Session 0) from launching GUI windows on user screens (Session 1+), we introduce a **two-process architecture**:
1. **Background Service / Daemon:** Continuously monitors the security log, captures camera snapshots, records geolocation, and updates SQLite.
2. **User Session Companion (`LoginCaptureUI.exe`):**
   - Runs in the user's desktop session at startup (minimized to system tray).
   - Listens for Windows Session Unlock events (`WTSRegisterSessionNotification` for `WTS_SESSION_UNLOCK` or Event 4624).
   - Queries `login_events.db` for any unacknowledged failed login attempts (`notification_status = 'PENDING'`).

#### UI Features & Layout (Modern Modern Desktop UI - PyQt6 / CustomTkinter / Webview)
- **Breach Alert Modal:**
  - Red / Amber alert banner: *"Intruder Alert: Failed Login Attempt Detected While You Were Away!"*
  - High-resolution preview of the intruder's photo.
  - Timestamp, targeted username/account, and number of consecutive failed attempts.
  - Interactive map preview or clickable Google Maps link with estimated address.
  - Action buttons:
    - **"Dismiss / Mark as Reviewed"** (updates status to `ACKNOWLEDGED`).
    - **"Save / Export Evidence"** (exports high-res photo + incident report PDF/image).
    - **"Open Full Incident History"**.
- **Management Dashboard:**
  - **Incident Gallery:** Grid view of all historical captured attempts with filters (by date, user).
  - **Live Camera Test:** Live preview to ensure webcam angle and lighting are optimal.
  - **Settings Panel:** Email notifications setup, storage policies, camera selection, and startup toggles.
  - **PIN Protection:** Optional Master PIN so an intruder cannot open the dashboard and delete their own captured photo.

---

### 3.4. Instant Alert Dispatch (Email & Notifications)

#### Goal
Immediately dispatch an email alert to the user's phone/inbox with full details and the intruder's snapshot attached.

#### Implementation Architecture
- **Transport Mechanism:**
  - Direct SMTP client (`smtplib` + `email.mime`) supporting SSL/TLS (Gmail App Passwords, Outlook/Office 365, Yahoo, custom SMTP, or SendGrid/Resend API).
- **Email Content:**
  - **Subject:** `🚨 Security Alert: Failed Login Attempt on [DeviceName]`
  - **Body (Rich HTML):**
    - Embedded inline photograph of the intruder (`cid:intruder_photo`).
    - Exact date and time (with local timezone).
    - User account targeted.
    - Public IP, City, Country, and ISP.
    - Direct Google Maps link for geolocation.
- **Offline Resilient Outbox Queue:**
  - If the machine has no Wi-Fi at the lock screen, the email task is written to an `email_queue` table in SQLite.
  - A background retry worker attempts transmission every 30 seconds once network connectivity is restored.

---

### 3.5. Storage Control & Automated Retention Policies

#### Goal
Prevent webcam photos and event logs from consuming excessive disk space, while ensuring recent security evidence is never prematurely deleted.

#### Implementation Architecture
- **Retention Rules (Configurable in UI):**
  1. **Time-Based Expiration:**
     - Retain photos for 7, 14, 30, 60, or 90 days (default: **30 days**).
     - Any photo and database record older than the threshold is automatically purged.
  2. **Storage Quota Cap:**
     - Maximum folder size limit (e.g., 200 MB, 500 MB, 1 GB).
     - When the limit is reached, a **FIFO (First-In, First-Out)** rotation cleans up the oldest photos until folder size drops below 80% of quota.
  3. **Event Count Limit:**
     - Option to keep only the last *N* events (e.g., last 100 failed logins).
- **Cleanup Engine:**
  - Background maintenance thread runs daily at midnight and after each new photo capture.
  - Also cleans up orphaned files (photos without DB entries, or DB entries with missing images).

---

## 4. Value-Added Features & Innovations (Recommended Additions)

To elevate this project from a standard hobby script into a professional, commercial-grade security tool, the following enhancements are recommended:

### 4.1. Instant Push Notification via Telegram Bot / Discord Webhook (Zero SMTP Hassle)
- Setting up SMTP passwords (especially Google App Passwords) can sometimes confuse non-technical users.
- **Telegram Bot Integration:** The user creates a free bot in 1 minute using `@BotFather` and enters their Bot Token + Chat ID in the app settings.
- **Result:** Within 2 seconds of a wrong password, the user's phone buzzes with a Telegram message containing the intruder's photo, timestamp, and location!

### 4.2. Burst-Shot Capture (Anti-Blur & Angle Optimization)
- Intruders often look down at the keyboard or move while entering passwords. A single frame might catch the back of a head or motion blur.
- **Solution:** Capture a rapid 3-frame burst (e.g., 0ms, 300ms, 600ms) or select the sharpest frame using OpenCV Laplacian variance (motion blur detector), saving the best image and attaching all 3 in the dashboard.

### 4.3. Anti-Spam & Intelligent Cooldown Filter
- If someone frantically types 10 wrong passwords in 15 seconds, we must avoid triggering 10 camera opens, 10 database writes, and 10 separate emails.
- **Grouping Rule:** If consecutive failed attempts occur within 30 seconds, group them into a single "Intrusion Incident", capturing 1-2 photos and sending 1 combined email with the total attempt count.

### 4.4. Stealth & Hardware Safety
- Some webcams have a green/white LED indicator that lights up.
- Minimize exposure: Rapid capture routine (<150ms total) with camera handle immediately closed to minimize LED glow time.
- Silent execution: All operations run asynchronously in worker threads so login screen responsiveness is never degraded.

### 4.5. Audit Policy Auto-Enforcement & Self-Healing
- Windows Home Edition or certain privacy tools occasionally reset security auditing.
- The service periodically checks if Audit Policy for `Logon Failure` is enabled; if disabled, it self-heals by running `auditpol`.

---

## 5. System Architecture & Component Diagram

```
+---------------------------------------------------------------------------------+
|                                WINDOWS MACHINE                                  |
+---------------------------------------------------------------------------------+
|                                                                                 |
|  [Lock Screen / Login Screen]                                                   |
|        │                                                                        |
|        ▼ (Wrong Password Entered)                                               |
|  [Windows Event Log: Security (Event 4625)]                                     |
|        │                                                                        |
|        ▼                                                                        |
|  +───────────────────────────────────────────────────────────────────────────+  |
|  | BACKGROUND DAEMON / SERVICE (Session 0 or SYSTEM Daemon)                  |  |
|  |  • Event Listener (Real-time EventLog Hook)                               |  |
|  |  • OpenCV Camera Engine (Fast Warmup & Burst Capture)                     |  |
|  |  • Network & Geolocation Resolver (IP + Wi-Fi Triangulation)              |  |
|  |  • SQLite Storage Engine (Encrypted metadata & image paths)               |  |
|  |  • Email / Telegram Dispatcher (With offline queuing)                     |  |
|  |  • Storage Retention Worker (30-day FIFO purge)                           |  |
|  +───────────────────────────────────────────────────────────────────────────+  |
|        │                                                                        |
|        ▼ (Legitimate User Successfully Logs in / Unlocks)                       |
|  [Windows Event: Logon / Unlock (Event 4624 / WTS_SESSION_UNLOCK)]              |
|        │                                                                        |
|        ▼                                                                        |
|  +───────────────────────────────────────────────────────────────────────────+  |
|  | USER COMPANION & DASHBOARD (Session 1+ Interactive GUI)                   |  |
|  |  • Runs in System Tray                                                    |  |
|  |  • Pops up "Breach Alert" Modal if unacknowledged attempts exist          |  |
|  |  • Incident Gallery & Evidence Export                                     |  |
|  |  • Settings Configurator (SMTP, Telegram, Storage Quotas, Master PIN)    |  |
|  +───────────────────────────────────────────────────────────────────────────+  |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

## 6. Database Schema Design (`login_events.db`)

To support geolocation, retention, and notification channels, the database schema will evolve:

```sql
-- Incidents & Login Events Table
CREATE TABLE IF NOT EXISTS login_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    record_number INTEGER NOT NULL UNIQUE,
    username TEXT,
    logon_type INTEGER,
    detected_at TEXT NOT NULL,
    image_path TEXT,
    
    -- Geolocation Telemetry
    public_ip TEXT,
    city TEXT,
    region TEXT,
    country TEXT,
    latitude REAL,
    longitude REAL,
    maps_url TEXT,
    location_status TEXT DEFAULT 'PENDING',  -- 'RESOLVED', 'OFFLINE', 'FAILED'
    
    -- Notifications Tracking
    email_status TEXT DEFAULT 'PENDING',     -- 'PENDING', 'SENT', 'FAILED'
    telegram_status TEXT DEFAULT 'PENDING',  -- 'PENDING', 'SENT', 'DISABLED'
    
    -- User UI Status
    reviewed_by_user INTEGER DEFAULT 0,      -- 0 = Unread/Trigger Popup, 1 = Reviewed
    
    created_at TEXT NOT NULL
);

-- Application Settings Table
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Default settings stored:
- `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `alert_email`
- `telegram_bot_token`, `telegram_chat_id`, `telegram_enabled`
- `retention_days` (default: 30)
- `storage_max_mb` (default: 500)
- `master_pin_hash` (optional security lock)
- `burst_count` (default: 1 or 2)

---

## 7. Technology Stack & Tools

| Component | Selected Technology | Rationale |
| :--- | :--- | :--- |
| **Core Service Engine** | Python 3.11+ / `pywin32` / `ctypes` | Native Windows EventLog and API hook integration |
| **Computer Vision** | `OpenCV` (headless / DirectShow backend) | Fastest camera initialization & capture (<150ms) |
| **Desktop UI / Dashboard** | `PyQt6` or `CustomTkinter` | Modern, dark-mode, native-feeling Windows application |
| **Geolocation** | `requests` / `urllib3` + IP Geolocation API | Fast, zero external API keys needed for basic mode |
| **Notification Services** | `smtplib` (Email) + Telegram Bot API | Redundant, instant alert delivery channels |
| **Packaging & Executable** | `PyInstaller` (One-File / One-Dir) | Compiles all dependencies into a standalone `.exe` |
| **Windows Installer** | `Inno Setup` | Clean, professional installation wizard with UAC handling |

---

## 8. Implementation Roadmap (Phases)

- [ ] **Phase 1: Architecture Restructuring & Path Generalization**
  - Migrate hardcoded paths to `%ProgramData%\WindowsLoginCapture`.
  - Upgrade SQLite schema for geolocation and notification states.
  - Implement dynamic config manager (`settings.json` or SQLite settings).

- [ ] **Phase 2: Geolocation & Email Alert Engine**
  - Add offline-safe IP Geolocation module with Google Maps link generation.
  - Add asynchronous SMTP email dispatcher with image attachment & offline queue.
  - (Optional) Add Telegram Bot one-click webhook notification.

- [ ] **Phase 3: Storage Control & Automated Retention Engine**
  - Implement FIFO rotation based on age (30-day default) and size (500MB default).
  - Add auto-cleanup routine at startup and post-capture.

- [ ] **Phase 4: Modern Desktop UI & Session Unlock Listener**
  - Develop the Breach Alert popup modal (shown upon user unlock).
  - Build the System Tray icon and Dashboard (Incident History, Settings, Camera Test).
  - Implement master PIN protection.

- [ ] **Phase 5: Packaging, Installer & Distribution (.exe)**
  - Configure PyInstaller spec files for silent background service and UI executable.
  - Build Inno Setup script with automatic `auditpol` policy configuration and Windows startup registration.
  - Test on clean Windows 10 & 11 environments without Python installed.

---

*Document created for review. Awaiting user feedback before proceeding with code implementation.*
