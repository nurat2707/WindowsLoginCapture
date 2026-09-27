# 🛡️ Windows Login Capture — User Guide

Welcome to **Windows Login Capture**! This application protects your Windows laptop by silently taking a photo of anyone who tries to guess or enters an incorrect password/PIN, tracking their physical location, sending an alert email to your phone, and popping up the evidence the moment you unlock your PC.

---

## ⚡ 1. Quick Installation (Takes 1 Minute)

1. Locate the installer file: **`WindowsLoginCapture_Setup_v1.0.exe`**.
2. **Right-click** on the `.exe` and choose **"Run as administrator"**.
3. Click **Next** $\rightarrow$ **Install**.
4. When installation finishes, the security suite starts automatically:
   * A **Shield icon** appears in your Windows System Tray (bottom-right near your clock).
   * A **Security Center** desktop shortcut is created on your Desktop.
   * The background monitoring service runs 24/7 silently as a native Windows service.

---

## 🔐 2. Setting Up Your Master PIN

The app has a **Master Security PIN** so that intruders cannot open Settings, disable the webcam, or delete captured photos.

1. Open **Windows Login Capture** (double-click the Desktop shortcut or click the System Tray shield icon).
2. Click the **Settings (Gear Icon ⚙️)** at the top right.
3. You will be prompted to create your **4-Digit Master PIN** (e.g. `1234`).
4. Enter your chosen PIN. Remember this PIN — you will need it whenever accessing Settings or purging incident history.

---

## 📧 3. Setting Up Real-Time Email Alerts (Gmail)

You can receive an instant email on your phone with the intruder's webcam photo and a Google Maps location link whenever an unauthorized attempt occurs.

To allow the app to send emails securely without exposing your main Google password, Google uses a **16-Character App Password**.

### Step A: Generate a Google 16-Character App Password
1. Open your browser and go to your Google Security settings:  
   👉 **[https://myaccount.google.com/security](https://myaccount.google.com/security)**
2. Make sure **2-Step Verification** is turned **ON** on your Google account.
3. Now go directly to the App Passwords page:  
   👉 **[https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**  
   *(If prompted, sign in again with your Google password).*
4. In the **App name** field, type: `Windows Login Capture` and click **Create**.
5. Google will display a popup with a **16-letter passkey** inside a yellow box (e.g., `abcd efgh ijkl mnop`).
6. **Copy** or write down this 16-letter code.

---

### Step B: Configure Email in the App
1. In the **Windows Login Capture** app, click **Settings ⚙️** (enter your Master PIN).
2. Look for the **Real-Time Email Alerts** card on the right:
   * **Recipient Alert Email:** Enter the email address where you want to receive alerts (e.g. `your_personal_email@gmail.com`).
   * **Sender Email Account:** Enter your Gmail address that generated the passkey (e.g. `your_sender_email@gmail.com`).
   * **16-Character App Password:** Paste the 16-character code you copied from Google.
3. Click **"Send Test Alert Email"**.
   * Check your inbox — you will receive a test notification confirming the connection!
4. Click the blue **"Save Changes"** button at the bottom right.

---

## 🎯 4. How It Works Day-to-Day

### 🚨 Scenario 1: Unauthorized Person Enters Wrong Password
* Someone approaches your locked laptop and types the wrong PIN or password.
* Within **5 milliseconds**, the system registers the attempt and silently triggers your laptop's webcam.
* The camera captures the intruder's photo.
* The system performs **Wi-Fi triangulation** to record the physical city (e.g., Coimbatore, Tamil Nadu) and GPS coordinates.
* If email alerts are enabled, an alert email with the photo and a Google Maps link is immediately dispatched to your phone.

### ✅ Scenario 2: You Unlock Your Laptop
* When you return and log in with your **correct password**, the **Security Center automatically pops up** on your screen.
* A prominent **red alert banner** informs you that an intruder was detected while you were away.
* You can immediately review their photo, the exact time of the attempt, and the location.

---

## 🖼️ 5. Key Features & Controls

* **Google Photos Lightbox Viewer:** Click any photo in the incident grid to open full-screen view. You can see the target Windows account, timestamp, IP address, and click **"Explore in Google Maps"**.
* **Date & Category Filters:** Quickly filter incidents by *Today*, *Yesterday*, *Last 7 Days*, or a custom date range.
* **Search Bar:** Search incidents by username or date.
* **Storage Meter:** The Settings tab displays a Google One-style storage gauge showing how much disk space photos are using. Old photos are automatically cleaned up after 30 days.
* **Maximize & Resize:** Double-click the top header bar or click the standard Windows maximize button to smoothly expand the window full screen.
* **System Tray Control:** Right-click the shield icon in the taskbar notification area to:
  * Open Security Center
  * View background service status (Protected / Active)
  * Exit companion

---

## ❓ 6. Frequently Asked Questions & Troubleshooting

#### Q: The camera didn't take a picture when I tested wrong password?
* Ensure Windows allows desktop apps to use the webcam:
  1. Open Windows **Settings** (`Win + I`) $\rightarrow$ **Privacy & Security** $\rightarrow$ **Camera**.
  2. Ensure **"Camera access"** is turned **ON**.
  3. Ensure **"Let desktop apps access your camera"** is turned **ON**.

#### Q: How do I change my Master PIN?
* Go to **Settings ⚙️** $\rightarrow$ enter your current PIN $\rightarrow$ scroll to **Master Security PIN** $\rightarrow$ type your new PIN $\rightarrow$ click **Save Changes**.

#### Q: How do I pause or stop monitoring temporarily?
* Open **Settings ⚙️** $\rightarrow$ toggle the **Background Service Protection** switch to OFF. You will need your Master PIN to do this.

#### Q: How do I completely uninstall the app?
* Open Windows **Settings** $\rightarrow$ **Installed apps** $\rightarrow$ search for **Windows Login Capture** $\rightarrow$ click **Uninstall**. The uninstaller automatically stops and cleans up the background service, scheduled tasks, and shortcuts.

---

*Enjoy peace of mind knowing your laptop is always protected!*
