"""
email_notifier.py
Asynchronously sends security alert emails with embedded webcam snapshot,
telemetry, and geolocation data via SMTP.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import config_manager

def send_alert_email(
    image_path: str,
    username: str,
    detected_at: str,
    ip_address: str = "Unknown",
    city: str = "Unknown",
    maps_url: str = "",
    accuracy_m: str = ""
) -> bool:
    """
    Sends an HTML alert email with the intruder's photo embedded.
    Returns True if sent successfully, False otherwise.
    """
    smtp_host = config_manager.get_setting("smtp_host", "smtp.gmail.com")
    smtp_port = int(config_manager.get_setting("smtp_port", "587"))
    smtp_user = config_manager.get_setting("smtp_user", "").strip()
    smtp_pass = config_manager.get_setting("smtp_password", "").strip()
    recipient = config_manager.get_setting("alert_email", "").strip()

    if not smtp_user or not smtp_pass or not recipient:
        print("[EMAIL] Skipping: SMTP credentials or recipient email not configured.")
        return False

    msg = MIMEMultipart("related")
    msg["Subject"] = f"🚨 Security Alert: Failed Login Attempt on Windows ({username or 'Unknown User'})"
    msg["From"] = smtp_user
    msg["To"] = recipient

    # HTML Body
    maps_html = f'<p><a href="{maps_url}" style="color: #1a73e8; font-weight: bold;" target="_blank">📍 Open Location in Google Maps</a></p>' if maps_url else '<p>Location: Unavailable / Offline</p>'
    acc_text = f" (~{accuracy_m}m accuracy)" if accuracy_m else ""

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e0e0e0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
          <div style="background-color: #d32f2f; color: #ffffff; padding: 18px 24px; text-align: center;">
            <h2 style="margin: 0; font-size: 20px;">🚨 Unauthorized Login Attempt Detected</h2>
          </div>
          <div style="padding: 24px; color: #333333;">
            <p style="font-size: 15px;">Someone entered an incorrect password or PIN on your Windows laptop.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px;">
              <tr style="border-bottom: 1px solid #eeeeee;"><td style="padding: 8px 0; color: #666;"><strong>Target Account:</strong></td><td>{username or 'Standard User'}</td></tr>
              <tr style="border-bottom: 1px solid #eeeeee;"><td style="padding: 8px 0; color: #666;"><strong>Timestamp:</strong></td><td>{detected_at}</td></tr>
              <tr style="border-bottom: 1px solid #eeeeee;"><td style="padding: 8px 0; color: #666;"><strong>Public IP:</strong></td><td>{ip_address}</td></tr>
              <tr style="border-bottom: 1px solid #eeeeee;"><td style="padding: 8px 0; color: #666;"><strong>City / Region:</strong></td><td>{city}{acc_text}</td></tr>
            </table>

            {maps_html}

            <div style="text-align: center; margin-top: 20px;">
              <p style="font-weight: bold; margin-bottom: 8px;">Captured Photo of Person at Laptop:</p>
              <img src="cid:intruder_photo" style="max-width: 100%; height: auto; border-radius: 6px; border: 2px solid #d32f2f;" alt="Intruder Photo" />
            </div>
          </div>
          <div style="background-color: #f9f9f9; padding: 12px; text-align: center; font-size: 12px; color: #888888;">
            Windows Login Capture Security System
          </div>
        </div>
      </body>
    </html>
    """

    msg_alternative = MIMEMultipart("alternative")
    msg.attach(msg_alternative)
    msg_alternative.attach(MIMEText(html_content, "html"))

    # Attach Photo Inline
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img_f:
                img_data = img_f.read()
                image_mime = MIMEImage(img_data)
                image_mime.add_header("Content-ID", "<intruder_photo>")
                image_mime.add_header("Content-Disposition", "inline", filename=os.path.basename(image_path))
                msg.attach(image_mime)
        except Exception as e:
            print(f"[EMAIL] Error attaching photo: {e}")

    # Send Email via SMTP
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"[EMAIL] Security alert successfully sent to {recipient}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send email: {e}")
        return False

# ----------------- SELF-TEST UTILITY -----------------
if __name__ == "__main__":
    print("--- Running email_notifier.py configuration test ---")
    current_email = config_manager.get_setting("alert_email")
    current_user = config_manager.get_setting("smtp_user")

    print(f"Current Configured Alert Email : {current_email or '(Not set yet)'}")
    print(f"Current SMTP Sender Account    : {current_user or '(Not set yet)'}")

    if not current_email or not current_user:
        print("\n[NOTE] SMTP is not configured yet. You can configure it anytime through the GUI,")
        print("or run a live test by setting them via config_manager.")
    else:
        print("\nAttempting to send a test email...")
        # Uses the latest captured image if available
        test_img = None
        for f in os.listdir(config_manager.BASE_DIR):
            if f.startswith("failed_login_") and f.endswith(".jpg"):
                test_img = os.path.join(config_manager.BASE_DIR, f)
                break

        send_alert_email(
            image_path=test_img,
            username="TestUser",
            detected_at="2026-09-26 22:00:00",
            ip_address="103.5.112.80",
            city="Coimbatore, Tamil Nadu",
            maps_url="https://www.google.com/maps",
            accuracy_m="92"
        )

    print("\n--- Self-test completed ---")
