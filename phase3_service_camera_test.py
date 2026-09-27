import cv2
import os
from datetime import datetime

OUTPUT_DIR = r"F:\WindowsLoginCapture"

print("Service-camera test starting...")
print("Running as:", os.getlogin())

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Service context could not open webcam.")
    raise SystemExit

print("Webcam opened successfully.")

ret, frame = camera.read()

if not ret:
    print("ERROR: Webcam opened, but frame capture failed.")
    camera.release()
    raise SystemExit

filename = os.path.join(
    OUTPUT_DIR,
    "service_camera_test_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg",
)

cv2.imwrite(filename, frame)
camera.release()

print("Photo captured successfully.")
print("Saved to:", filename)
