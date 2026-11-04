; Windows-Installer (Inno Setup 6) – wird in der CI gebaut:
;   iscc /DMyVersion=X.Y.Z /DSrcDir=<dist\SH-Tunebridge> /DWebView2=<MicrosoftEdgeWebview2Setup.exe> /DOutDir=<out> sh-tunebridge.iss
; Installiert nur für den aktuellen Benutzer (keine Adminrechte), legt Startmenü-/Desktop-Verknüpfung an,
; trägt sich in „Apps & Features“ ein und installiert Microsoft Edge WebView2 mit, falls es fehlt.
; Die Daten (%LOCALAPPDATA%\SH-Tunebridge) bleiben beim Deinstallieren erhalten.

#ifndef MyVersion
  #error MyVersion fehlt
#endif

[Setup]
; Gleiche AppId wie in src/tunebridge/winapp.py (APP_ID) – nie ändern, sonst gibt es zwei Einträge
AppId={{6B1E3C1A-5D2F-4C8E-9A7B-3F1D2E4C5A6B}
AppName=SH-Tunebridge
AppVersion={#MyVersion}
AppVerName=SH-Tunebridge {#MyVersion}
AppPublisher=Bigsmoke002
AppPublisherURL=https://github.com/Bigsmoke002/SH-Tunebridge
AppSupportURL=https://github.com/Bigsmoke002/SH-Tunebridge/issues
DefaultDirName={autopf}\SH-Tunebridge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\..\src\tunebridge\web\static\icon.ico
UninstallDisplayIcon={app}\SH-Tunebridge.exe
UninstallDisplayName=SH-Tunebridge
OutputDir={#OutDir}
OutputBaseFilename=SH-Tunebridge-{#MyVersion}-windows-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto
CloseApplications=force
RestartApplications=no
LicenseFile=..\..\LICENSE

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
de.WV2Status=Microsoft Edge WebView2 wird installiert (für das App-Fenster) …
en.WV2Status=Installing Microsoft Edge WebView2 (needed for the app window) …
de.Launch=SH-Tunebridge jetzt starten
en.Launch=Start SH-Tunebridge now

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#WebView2}"; DestDir: "{tmp}"; DestName: "MicrosoftEdgeWebview2Setup.exe"; Flags: deleteafterinstall; Check: NeedsWebView2

[InstallDelete]
; Reste einer älteren Version (Programmteile werden komplett neu geschrieben)
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\SH-Tunebridge"; Filename: "{app}\SH-Tunebridge.exe"
Name: "{autodesktop}\SH-Tunebridge"; Filename: "{app}\SH-Tunebridge.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "{cm:WV2Status}"; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\SH-Tunebridge.exe"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WV2 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(Root: Integer; Key: String): Boolean;
var
  V: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasVersion(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2) or
                 HasVersion(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2) or
                 HasVersion(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WV2));
end;
