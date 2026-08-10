# Builds the Windows app and packages it as a single Setup.exe installer
# (Inno Setup) — that Setup.exe is the ONLY file you upload to the GitHub
# release; the in-app updater downloads and silent-installs it too.
# Usage: .\build_exe.ps1
# Requires Inno Setup (free, one-time): https://jrsoftware.org/isdl.php

$ErrorActionPreference = "Stop"

$version = (python -c "import sys; sys.path.insert(0, 'translator'); from app.version import APP_VERSION; print(APP_VERSION)").Trim()
Write-Host "Building Dubify AI v$version..."

pip install --quiet pyinstaller pyinstaller-hooks-contrib

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

python -m PyInstaller dubify.spec --noconfirm --clean

$isccPath = $null
$isccCmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($isccCmd) { $isccPath = $isccCmd.Source }
if (-not $isccPath) {
    $knownPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (Test-Path $knownPath) { $isccPath = $knownPath }
}
if (-not $isccPath) {
    Write-Host ""
    Write-Host "ERROR: Inno Setup (ISCC.exe) not found."
    Write-Host "Install it (free): https://jrsoftware.org/isdl.php, then re-run this script."
    exit 1
}

& $isccPath "installer.iss" "/DMyAppVersion=$version"

$setupName = "dist\DubifyAI-Setup-v$version.exe"
Write-Host ""
Write-Host "Installer ready: $setupName"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Bump APP_VERSION in translator/app/version.py for the NEXT release (not this one)."
Write-Host "  2. On GitHub -> Releases -> Draft a new release -> tag 'v$version' -> upload $setupName as the ONLY asset."
Write-Host "  3. Publish. Friends running an older version see the Update button next launch; clicking it"
Write-Host "     downloads this same Setup.exe and silent-installs it over the old version, then restarts."
