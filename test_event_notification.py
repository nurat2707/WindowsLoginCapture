import win32evtlog
import win32event

print("Opening Security log...")

handle = win32evtlog.OpenEventLog("localhost", "Security")

event = win32event.CreateEvent(None, 0, 0, None)

print("Registering for Security log changes...")

win32evtlog.NotifyChangeEventLog(handle, event)

print("Waiting for a Security log change...")
print("Now enter a WRONG password at the Windows login screen.")

result = win32event.WaitForSingleObject(event, 30000)

if result == win32event.WAIT_OBJECT_0:
    print("\nSUCCESS!")
    print("Windows notified Python that the Security log changed.")

else:
    print("\nTIMEOUT!")
    print("No notification was received within 30 seconds.")

win32evtlog.CloseEventLog(handle)
win32event.CloseHandle(event)
