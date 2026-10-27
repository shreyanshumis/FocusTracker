#define AppName "Blacklist"
#define AppVersion "1.4.0"

[Setup]
AppId={{17F788B9-ED51-4C8C-966E-AF5105B12560}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Blacklist
DefaultDirName={autopf}\Blacklist
DefaultGroupName=Blacklist
DisableProgramGroupPage=yes
UsePreviousGroup=no
DisableDirPage=yes
OutputDir=installer-output
OutputBaseFilename=Blacklist-Setup-1.4.0
SetupIconFile=build\focus.ico
UninstallDisplayIcon={app}\Blacklist.exe
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
VersionInfoVersion=1.4.0.0
VersionInfoDescription=Blacklist Windows Setup
UninstallDisplayName=Blacklist

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[InstallDelete]
Type: files; Name: "{commonprograms}\FocusTracker\FocusTracker.lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Focus Harbor.lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Recover blocked websites.lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Preview (no blocking).lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Browser companion folder.lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Setup instructions.lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Uninstall FocusTracker.lnk"
Type: files; Name: "{commonprograms}\FocusTracker\Uninstall Focus Harbor.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\FocusTracker.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Focus Harbor.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Recover blocked websites.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Preview (no blocking).lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Browser companion folder.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Setup instructions.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Uninstall FocusTracker.lnk"
Type: files; Name: "{commonprograms}\Focus Harbor\Uninstall Focus Harbor.lnk"

Type: files; Name: "{app}\FocusTracker.exe"
Type: files; Name: "{group}\FocusTracker.lnk"
Type: files; Name: "{commondesktop}\FocusTracker.lnk"
Type: files; Name: "{app}\youtube-extension\logo.png"
Type: files; Name: "{app}\FocusHarbor.exe"
Type: files; Name: "{group}\Focus Harbor.lnk"
Type: files; Name: "{group}\Uninstall Focus Harbor.lnk"
Type: files; Name: "{commondesktop}\Focus Harbor.lnk"
Type: files; Name: "{userdesktop}\Focus Harbor.lnk"

Type: files; Name: "{group}\Recover blocked websites.lnk"
Type: files; Name: "{group}\Preview (no blocking).lnk"
Type: files; Name: "{group}\Browser companion folder.lnk"
Type: files; Name: "{group}\Setup instructions.lnk"
Type: files; Name: "{group}\Uninstall Blacklist.lnk"

[Files]
Source: "dist-study\Blacklist.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALL-NOTES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\Recover websites.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\youtube-extension\*"; DestDir: "{app}\youtube-extension"; Flags: ignoreversion recursesubdirs createallsubdirs

Source: "dist-study\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist-study\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Blacklist"; Filename: "{app}\Blacklist.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Blacklist"; Filename: "{app}\Blacklist.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Blacklist.exe"; Description: "Launch Blacklist"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent runascurrentuser

[Code]
function InitializeUninstall(): Boolean;
var
  ExitCode: Integer;
begin
  Result := False;
  if not Exec(ExpandConstant('{app}\Blacklist.exe'), '--uninstall-cleanup', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    MsgBox('Website-rule cleanup could not start. Blacklist has not been removed. Run Recover websites.cmd in the installation folder, then retry.', mbError, MB_OK);
    Exit;
  end;
  if ExitCode <> 0 then
  begin
    MsgBox('Website rules could not be safely removed. Blacklist has not been removed. Close any running copy and run Recover websites.cmd in the installation folder, then retry.', mbError, MB_OK);
    Exit;
  end;
  Result := True;
end;
