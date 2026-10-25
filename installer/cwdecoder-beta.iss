; CW Decoder — Copyright (C) 2026 DF1DS (kainomatic) — SPDX-License-Identifier: GPL-3.0-or-later
; Inno-Setup-Skript, Beta-Variante (ADR-0012), parallel zur Stable installierbar.
; Gegenstück: installer/cwdecoder.iss — beide Dateien synchron halten.
;
; AppId {D14A0CE4-9839-4396-9C0C-EEE7AFA3DA84} — NIEMALS ÄNDERN.
; Windows erkennt Updates und Deinstallation an dieser GUID; eine neue GUID
; ergäbe eine zweite, parallele Installation.
;
; APP_VERSION setzt der Release-Workflow per /DAPP_VERSION=X.Y.Z (ADR-0014);
; ohne /D gilt der Wert unten.

#ifndef APP_VERSION
  #define APP_VERSION "0.1.0"
#endif

#define APP_NAME "CW Decoder Beta"
#define APP_EXE "CWDecoder.exe"
#define APP_DATA_DIR "CWDecoder-Beta"

[Setup]
AppId={{D14A0CE4-9839-4396-9C0C-EEE7AFA3DA84}
AppName={#APP_NAME}
AppVersion={#APP_VERSION}
AppVerName={#APP_NAME} {#APP_VERSION}
AppPublisher=DF1DS (kainomatic)
AppPublisherURL=https://github.com/kainomatic/cw-decoder
AppSupportURL=https://github.com/kainomatic/cw-decoder/issues
AppUpdatesURL=https://github.com/kainomatic/cw-decoder/releases
DefaultDirName={autopf}\{#APP_NAME}
DefaultGroupName={#APP_NAME}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CWDecoder-Beta-Setup-v{#APP_VERSION}
SetupIconFile=..\assets\cwdecoder.ico
UninstallDisplayIcon={app}\{#APP_EXE}
UninstallDisplayName={#APP_NAME}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; Laufende Instanz erkennen und schließen (ADR-0013). Den Neustart nach dem
; Self-Update übernimmt der [Run]-Eintrag mit ShouldRestartApp, nicht der
; Restart Manager.
AppMutex=CWDecoder-Beta
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
german.RemoveUserData=Sollen auch die Einstellungen und Logs des {#APP_NAME} gelöscht werden?%n%n%1%n%nEmpfehlung: Nein – dann bleiben sie für eine spätere Installation erhalten. Aufnahmen unter Dokumente\CW Decoder werden nie gelöscht.
english.RemoveUserData=Also delete the settings and logs of {#APP_NAME}?%n%n%1%n%nRecommended: No – they are kept for a later installation. Recordings in Documents\CW Decoder are never deleted.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\CWDecoder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Reste einer älteren Version im Bundle-Ordner entfernen
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE}"
Name: "{group}\{cm:UninstallProgram,{#APP_NAME}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE}"; Tasks: desktopicon

[Run]
; Interaktive Installation: Haken "CW Decoder starten" auf der letzten Seite.
Filename: "{app}\{#APP_EXE}"; Description: "{cm:LaunchProgram,{#APP_NAME}}"; Flags: nowait postinstall runascurrentuser skipifsilent
; Self-Update (/SILENT /RESTARTCWDECODER): Programm automatisch neu starten.
Filename: "{app}\{#APP_EXE}"; Flags: nowait runascurrentuser; Check: ShouldRestartApp

[Code]
{ Neustart nur beim Self-Update: still UND mit /RESTARTCWDECODER aufgerufen.
  Ein stilles Verteilen ohne den Schalter startet das Programm nicht. }
function ShouldRestartApp: Boolean;
begin
  Result := WizardSilent() and (Pos('/RESTARTCWDECODER', UpperCase(GetCmdTail)) > 0);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\{#APP_DATA_DIR}');
    if DirExists(DataDir) then
      if SuppressibleMsgBox(FmtMessage(CustomMessage('RemoveUserData'), [DataDir]),
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
