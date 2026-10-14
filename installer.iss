#define AppName "FocusTracker"
#define AppVersion "1.3.4"

[Setup]
AppId={{17F788B9-ED51-4C8C-966E-AF5105B12560}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=FocusTracker
DefaultDirName={autopf}\FocusTracker
DefaultGroupName=FocusTracker
DisableProgramGroupPage=yes
DisableDirPage=yes
OutputDir=installer-output
OutputBaseFilename=FocusTracker-Setup-1.3.4
SetupIconFile=build\focus.ico
UninstallDisplayIcon={app}\FocusTracker.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=admin
AppMutex=Global\FocusHarbor,Global\FocusHarborPreview
CloseApplications=no
RestartApplications=no
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
VersionInfoVersion=1.3.4.0
VersionInfoDescription=FocusTracker Windows Setup
UninstallDisplayName=FocusTracker

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[InstallDelete]
Type: files; Name: "{app}\FocusHarbor.exe"
Type: files; Name: "{group}\Focus Harbor.lnk"
Type: files; Name: "{group}\Uninstall Focus Harbor.lnk"
Type: files; Name: "{commondesktop}\Focus Harbor.lnk"
Type: files; Name: "{userdesktop}\Focus Harbor.lnk"

[Files]
Source: "dist-study\FocusTracker.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALL-NOTES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\youtube-extension\*"; DestDir: "{app}\youtube-extension"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "dist-study\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FocusTracker"; Filename: "{app}\FocusTracker.exe"; WorkingDir: "{app}"
Name: "{group}\Recover blocked websites"; Filename: "{app}\FocusTracker.exe"; Parameters: "--unblock"; WorkingDir: "{app}"
Name: "{group}\Preview (no blocking)"; Filename: "{app}\FocusTracker.exe"; Parameters: "--demo"; WorkingDir: "{app}"
Name: "{group}\Browser companion folder"; Filename: "{app}\youtube-extension"
Name: "{group}\Setup instructions"; Filename: "{app}\INSTALL-NOTES.txt"
Name: "{group}\Uninstall FocusTracker"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FocusTracker"; Filename: "{app}\FocusTracker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FocusTracker.exe"; Description: "Launch FocusTracker"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent runascurrentuser

[Code]
function InitializeUninstall(): Boolean;
var
  ExitCode: Integer;
begin
  Result := False;
  if not Exec(ExpandConstant('{app}\FocusTracker.exe'), '--uninstall-cleanup', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    MsgBox('Website-rule cleanup could not start. FocusTracker has not been removed. Use Recover blocked websites from the Start menu, then retry.', mbError, MB_OK);
    Exit;
  end;
  if ExitCode <> 0 then
  begin
    MsgBox('Website rules could not be safely removed. FocusTracker has not been removed. Close any running copy and use Recover blocked websites, then retry.', mbError, MB_OK);
    Exit;
  end;
  Result := True;
end;
