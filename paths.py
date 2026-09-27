"""
paths.py
Centralized path resolution for Windows Login Capture.
Supports both local source development and compiled PyInstaller executable environments.
"""

import os
import sys

def get_base_dir() -> str:
    """Returns directory containing the application binaries or source scripts."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_ui_dir() -> str:
    """Returns directory containing web assets (HTML, CSS, JS)."""
    # PyInstaller temporary bundle directory (onefile mode)
    if hasattr(sys, "_MEIPASS"):
        bundled_ui = os.path.join(sys._MEIPASS, "ui")
        if os.path.exists(bundled_ui):
            return bundled_ui

    # PyInstaller onedir mode (_internal/ui)
    internal_ui = os.path.join(get_base_dir(), "_internal", "ui")
    if os.path.exists(internal_ui):
        return internal_ui

    # Local development or installed alongside binaries
    base_ui = os.path.join(get_base_dir(), "ui")
    return base_ui

def get_data_dir() -> str:
    """
    Returns directory for writable application data (database, captured photos, logs).
    In local dev: uses the local project folder.
    In production .exe: uses standard Windows %ProgramData%\\WindowsLoginCapture.
    """
    base_dir = get_base_dir()

    # If running from source folder in development, keep data local
    if not getattr(sys, "frozen", False) and os.path.exists(os.path.join(base_dir, "phase2_service.py")):
        return base_dir

    # In production install (.exe), use shared %ProgramData%
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    prod_data_dir = os.path.join(program_data, "WindowsLoginCapture")
    try:
        os.makedirs(prod_data_dir, exist_ok=True)
        return prod_data_dir
    except Exception:
        return base_dir

# Export primary directories
BASE_DIR = get_base_dir()
UI_DIR = get_ui_dir()
DATA_DIR = get_data_dir()

# Export specific file paths
DB_FILE = os.path.join(DATA_DIR, "login_events.db")
LOG_FILE = os.path.join(DATA_DIR, "failed_logins.txt")
PHOTOS_DIR = DATA_DIR
HTML_INDEX = os.path.join(UI_DIR, "index.html")
