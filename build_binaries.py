"""
build_binaries.py
Automated PyInstaller build script for Windows Login Capture.
Compiles a commercial-grade, standalone directory bundle containing:
  1. WindowsLoginCaptureService.exe (Background Service Daemon)
  2. WindowsLoginCaptureUI.exe      (System Tray Companion & Security Center UI)
  3. Shared DLLs and UI web assets (no %TEMP% extraction!)
"""

import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_FILE = os.path.join(BASE_DIR, "WindowsLoginCapture.spec")
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")

def check_pyinstaller():
    try:
        import PyInstaller
        print(f"[BUILD] Found PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("[BUILD ERROR] PyInstaller is not installed. Run: pip install pyinstaller")
        sys.exit(1)

def build_all():
    print("\n" + "=" * 60)
    print("[BUILD] Compiling unified WindowsLoginCapture application bundle...")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        SPEC_FILE
    ]
    
    subprocess.check_call(cmd, cwd=BASE_DIR)
    print("[BUILD SUCCESS] Application bundle compiled successfully.")

def main():
    check_pyinstaller()
    build_all()

    print("\n" + "=" * 60)
    print("[SUCCESS] BUILD COMPLETE!")
    print(f"Application package is located in: {os.path.join(DIST_DIR, 'WindowsLoginCapture')}")
    print("  - WindowsLoginCaptureService.exe")
    print("  - WindowsLoginCaptureUI.exe")
    print("  - UI assets and native libraries")
    print("=" * 60)

if __name__ == "__main__":
    main()
