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
SetupIconFile=translator\app\assets\logo.ico
Compression=lzma2
SolidCompression=yes
; Per-user install under %LOCALAPPDATA% — no admin prompt, and the in-app
; auto-updater (robocopy) needs write access to this folder without elevation.
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
; python3.dll is excluded here and relinked below via [Run]/mklink instead of
; being copied as a plain file — see the comment there for why.
Source: "dist\DubifyAI\*"; DestDir: "{app}"; Excludes: "_internal\python3.dll"; Flags: recursesubdirs ignoreversion

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Icons]
Name: "{group}\Dubify AI"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\Dubify AI"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; On this build machine, python3.dll is a symlink alias for python313.dll
; rather than the usual small stable-ABI forwarder stub. build_exe.ps1
; hardlinks them in dist\DubifyAI so PySide6/shiboken6 (which load python3.dll
; by name) resolve to the SAME loaded module as python313.dll instead of a
; second, independent copy of the CPython runtime (which access-violates the
; instant any abi3 extension touches it). Inno Setup's [Files] copy does not
; preserve hardlinks, so it's excluded above and recreated here post-install.
; "del" first: on an UPDATE (not a fresh install), python313.dll just got
; overwritten by the [Files] copy above, which creates a brand-new file — that
; silently breaks any hardlink from a previous install, leaving a stale
; python3.dll behind that makes mklink fail with "file already exists" (and
; since this runs hidden, that failure was invisible). Deleting it first makes
; this idempotent across both fresh installs and updates.
Filename: "cmd.exe"; Parameters: "/c del /f /q ""{app}\_internal\python3.dll"" >nul 2>&1 & mklink /H ""{app}\_internal\python3.dll"" ""{app}\_internal\python313.dll"""; Flags: runhidden; StatusMsg: "Finalizing installation..."
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Dubify AI"; Flags: nowait postinstall skipifsilent
