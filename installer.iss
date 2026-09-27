; Script generated for Windows Login Capture
; Commercial Standalone Windows Security Suite Installer

#define MyAppName "Windows Login Capture"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "LoginCapture Security"
#define MyAppURL "https://github.com/nurat2707/WindowsLoginCapture"
#define MyAppExeName "WindowsLoginCaptureUI.exe"
#define MyServiceExeName "WindowsLoginCaptureService.exe"

[Setup]
AppId={{9B7F1B5C-274A-4D39-9528-65DF38B6B788}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\WindowsLoginCapture
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=WindowsLoginCapture_Setup_v1.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
CloseApplications=force

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start companion automatically when Windows boots"; GroupDescription: "Startup Options:"; Flags: checkedonce

[Dirs]
; Shared ProgramData folder with modify permissions for both SYSTEM service and user UI
Name: "{commonappdata}\WindowsLoginCapture"; Permissions: authusers-modify

[Files]
; Unified Application Bundle (all executables, dependencies, and web UI)
Source: "dist\WindowsLoginCapture\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ui\*"; DestDir: "{app}\ui"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Windows Startup Run key for the tray companion
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "WindowsLoginCapture"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; 1. Enable Windows Logon Failure and Unlock Auditing in Windows Security Log
Filename: "auditpol.exe"; Parameters: "/set /subcategory:""Logon"" /failure:enable /success:enable"; Flags: runhidden; StatusMsg: "Configuring Windows Security Audit Policies..."
Filename: "auditpol.exe"; Parameters: "/set /subcategory:""Other Logon/Logoff Events"" /success:enable"; Flags: runhidden; StatusMsg: "Configuring Workstation Unlock Audit Policies..."

; 2. Register Windows Scheduled Task for Screen Unlock Check
Filename: "schtasks.exe"; Parameters: "/create /tn ""WindowsLoginCaptureUnlockCheck"" /tr """"{app}\{#MyAppExeName}"""" --check-unlock"" /sc onlogon /rl highest /f"; Flags: runhidden; StatusMsg: "Registering Unlock Event Handler..."

; 3. Register Windows Background Service
Filename: "{app}\{#MyServiceExeName}"; Parameters: "--startup=auto install"; Flags: runhidden; StatusMsg: "Registering Windows Background Service..."

; 4. Start Windows Background Service
Filename: "net.exe"; Parameters: "start WindowsLoginCapture"; Flags: runhidden; StatusMsg: "Starting Intruder Protection Daemon..."

; 5. Start Tray Companion in User Session Immediately
Filename: "{app}\{#MyAppExeName}"; Parameters: "--tray"; Flags: nowait runasoriginaluser

; 6. Launch Desktop Security Center UI
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall runasoriginaluser

[UninstallRun]
; Stop and remove service and tasks before files are deleted
Filename: "taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden
Filename: "schtasks.exe"; Parameters: "/delete /tn ""WindowsLoginCaptureUnlockCheck"" /f"; Flags: runhidden
Filename: "net.exe"; Parameters: "stop WindowsLoginCapture"; Flags: runhidden
Filename: "{app}\{#MyServiceExeName}"; Parameters: "remove"; Flags: runhidden

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // Terminate any running UI companion
  Exec('taskkill.exe', '/F /IM WindowsLoginCaptureUI.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  // Stop background service if running so the binary is not locked
  Exec('net.exe', 'stop WindowsLoginCapture', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

