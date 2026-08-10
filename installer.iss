; Inno Setup script — packages the PyInstaller onedir build (dist\DubifyAI)
; into a single Setup.exe for friends to download and run.
; Requires Inno Setup (free): https://jrsoftware.org/isdl.php
; Built by build_exe.ps1 via: ISCC installer.iss /DMyAppVersion=<version>

#define MyAppName "Dubify AI"
#define MyAppExeName "DubifyAI.exe"
#define MyAppPublisher "Dubify AI"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{6C6F9C6C-6E1F-4B2E-9A3C-DUBIFYAI0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\DubifyAI
DefaultGroupName=Dubify AI
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=DubifyAI-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
; Per-user install under %LOCALAPPDATA% — no admin prompt, and the in-app
; auto-updater (robocopy) needs write access to this folder without elevation.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\DubifyAI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Icons]
Name: "{group}\Dubify AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\Dubify AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Dubify AI"; Flags: nowait postinstall skipifsilent
