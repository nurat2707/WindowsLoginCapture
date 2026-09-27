import win32service
import win32serviceutil
import win32event
import servicemanager
import cv2
import os
from datetime import datetime


class CameraTestService(win32serviceutil.ServiceFramework):

    _svc_name_ = "WindowsLoginCameraTest"
    _svc_display_name_ = "Windows Login Camera Test"
    _svc_description_ = "Temporary service for testing webcam access."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Camera test service started.")

        output = r"F:\WindowsLoginCapture"

        servicemanager.LogInfoMsg("Attempting to open webcam...")

        camera = cv2.VideoCapture(0)

        if not camera.isOpened():
            servicemanager.LogErrorMsg("FAILED: Service could not open webcam.")
            return

        servicemanager.LogInfoMsg("SUCCESS: Service opened webcam.")

        ret, frame = camera.read()

        if not ret:
            servicemanager.LogErrorMsg(
                "FAILED: Service opened webcam but could not capture frame."
            )
            camera.release()
            return

        filename = os.path.join(
            output,
            "service_actual_camera_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".jpg",
        )

        cv2.imwrite(filename, frame)
        camera.release()

        servicemanager.LogInfoMsg("SUCCESS: Service captured photo: " + filename)

        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(CameraTestService)
