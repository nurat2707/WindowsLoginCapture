import cv2
from datetime import datetime

print("Opening webcam...")

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("ERROR: Could not open webcam.")
    input("Press Enter to exit...")
    raise SystemExit

print("Webcam opened successfully.")

ret, frame = camera.read()

if not ret:
    print("ERROR: Could not capture frame.")
    camera.release()
    input("Press Enter to exit...")
    raise SystemExit

filename = (
    "F:\\WindowsLoginCapture\\"
    + "test_photo_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".jpg"
)

cv2.imwrite(filename, frame)

camera.release()

print("Photo captured successfully.")
print("Saved to:")
print(filename)

input("Press Enter to exit...")
