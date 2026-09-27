# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a_service = Analysis(
    ['F:/WindowsLoginCapture/phase2_service.py'],
    pathex=['F:/WindowsLoginCapture'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'win32timezone',
        'win32service',
        'win32serviceutil',
        'win32event',
        'servicemanager',
        'cv2'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz_service = PYZ(a_service.pure, a_service.zipped_data, cipher=block_cipher)

exe_service = EXE(
    pyz_service,
    a_service.scripts,
    [],
    exclude_binaries=True,
    name='WindowsLoginCaptureService',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

a_ui = Analysis(
    ['F:/WindowsLoginCapture/tray_companion.py'],
    pathex=['F:/WindowsLoginCapture'],
    binaries=[],
    datas=[('F:/WindowsLoginCapture/ui', 'ui')],
    hiddenimports=[
        'webview',
        'clr',
        'win32ts',
        'win32gui',
        'win32con',
        'win32api',
        'win32process'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz_ui = PYZ(a_ui.pure, a_ui.zipped_data, cipher=block_cipher)

exe_ui = EXE(
    pyz_ui,
    a_ui.scripts,
    [],
    exclude_binaries=True,
    name='WindowsLoginCaptureUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_service,
    a_service.binaries,
    a_service.zipfiles,
    a_service.datas,
    exe_ui,
    a_ui.binaries,
    a_ui.zipfiles,
    a_ui.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WindowsLoginCapture',
)
