; EYEWAZ Urdu Voice - Inno Setup installer.
;
; Lays down the SAPI5 voice DLL, a NO-Python frozen speech server, the piper
; runtime and both trained voices; registers the voice with SAPI; and starts the
; server hidden at every logon so "EYEWAZ Urdu (Female/Male)" is always available
; in JAWS, Narrator, Word Read Aloud, and Control Panel > Speech.
;
; Build it with installer\build-installer.ps1 (which stages files into stage\ and
; invokes iscc). Do not run iscc by hand unless stage\ is already populated.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{1EDD25DC-D5F6-4C64-92F1-0C9E2C213CD5}
AppName=EYEWAZ Urdu Voice
AppVersion={#AppVersion}
AppPublisher=WAJD AI
AppPublisherURL=https://www.eyewaz.com
DefaultDirName={autopf}\EYEWAZ Urdu Voice
DisableProgramGroupPage=yes
DisableDirPage=yes
UninstallDisplayName=EYEWAZ Urdu Voice
UninstallDisplayIcon={app}\eyewaz-voice-server.exe
OutputDir=Output
OutputBaseFilename=EyewazUrduVoiceSetup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
; Native 64-bit install on both x64 and Windows-on-ARM. Ship the DLL/server that
; matches the host arch (build-installer.ps1 -Arch x64 for JAWS machines).
ArchitecturesInstallIn64BitMode=x64 arm64
WizardStyle=modern

[Files]
Source: "stage\EyewazTts.dll";          DestDir: "{app}";         Flags: ignoreversion
Source: "stage\eyewaz-voice-server.exe"; DestDir: "{app}";        Flags: ignoreversion
Source: "start-server.vbs";              DestDir: "{app}";        Flags: ignoreversion
Source: "register-task.ps1";             DestDir: "{app}";        Flags: ignoreversion
Source: "stage\piper\*";                 DestDir: "{app}\piper";   Flags: ignoreversion recursesubdirs createallsubdirs
Source: "stage\voices\*";                DestDir: "{app}\voices";  Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
Type: filesandordirs; Name: "{app}\piper"
Type: filesandordirs; Name: "{app}\voices"

[Code]
const
  TASK_NAME = 'EYEWAZ Urdu Voice Server';

procedure CurStepChanged(CurStep: TSetupStep);
var
  Rc: Integer;
  App: String;
begin
  if CurStep <> ssPostInstall then Exit;
  App := ExpandConstant('{app}');

  { Register both SAPI voice tokens (DllRegisterServer). Installer is elevated. }
  Exec('regsvr32.exe', '/s "' + App + '\EyewazTts.dll"', '',
       SW_HIDE, ewWaitUntilTerminated, Rc);

  { Create/replace the logon task that launches the hidden server. Done via
    register-task.ps1 (Register-ScheduledTask) so the space in "Program Files"
    can't break schtasks /tr quoting. }
  Exec('powershell.exe',
       '-NoProfile -ExecutionPolicy Bypass -File "' + App + '\register-task.ps1"',
       '', SW_HIDE, ewWaitUntilTerminated, Rc);

  { Start it now so the voice works without waiting for the next logon. }
  Exec('wscript.exe', '"' + App + '\start-server.vbs"', '',
       SW_HIDE, ewNoWait, Rc);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Rc: Integer;
  App: String;
begin
  if CurUninstallStep <> usUninstall then Exit;
  App := ExpandConstant('{app}');

  Exec('schtasks.exe', '/delete /f /tn "' + TASK_NAME + '"', '',
       SW_HIDE, ewWaitUntilTerminated, Rc);
  Exec('taskkill.exe', '/f /im eyewaz-voice-server.exe', '',
       SW_HIDE, ewWaitUntilTerminated, Rc);
  Exec('regsvr32.exe', '/u /s "' + App + '\EyewazTts.dll"', '',
       SW_HIDE, ewWaitUntilTerminated, Rc);
end;
