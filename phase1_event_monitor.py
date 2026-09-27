import time
import win32evtlog

SERVER = "localhost"
LOG_NAME = "Security"
EVENT_ID = 4625


def get_latest_event_record_id():
    hand = win32evtlog.OpenEventLog(SERVER, LOG_NAME)

    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

    events = win32evtlog.ReadEventLog(hand, flags, 0)

    if not events:
        win32evtlog.CloseEventLog(hand)
        return None

    latest = events[0]
    record_id = latest.RecordNumber

    win32evtlog.CloseEventLog(hand)
    return record_id


def check_for_failed_login(last_record_id):
    hand = win32evtlog.OpenEventLog(SERVER, LOG_NAME)

    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

    events = win32evtlog.ReadEventLog(hand, flags, 0)

    win32evtlog.CloseEventLog(hand)

    if not events:
        return last_record_id

    for event in reversed(events):
        if event.RecordNumber <= last_record_id:
            continue

        event_id = event.EventID & 0xFFFF

        if event_id == EVENT_ID:
            print("=" * 60)
            print("FAILED LOGIN DETECTED!")
            print(f"Event ID   : {event_id}")
            print(f"Record ID  : {event.RecordNumber}")
            print(f"Time       : {event.TimeGenerated}")
            print(f"Source     : {event.SourceName}")
            print("\nEvent Data:")

    for item in event.StringInserts or []:
        print(f"  {item}")

    print("=" * 60)

    return events[0].RecordNumber


def main():
    print("Windows Failed Login Monitor")
    print("Monitoring Security Event ID 4625...")
    print("Press Ctrl+C to stop.\n")

    last_record_id = get_latest_event_record_id()

    if last_record_id is None:
        print("Could not read the Security event log.")
        return

    print(f"Starting from Security record: {last_record_id}")

    try:
        while True:
            last_record_id = check_for_failed_login(last_record_id)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
