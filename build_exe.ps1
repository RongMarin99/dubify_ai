# Builds the Windows app and packages it as a single Setup.exe installer
# (Inno Setup) — that Setup.exe is the ONLY file you upload to the GitHub
# release; the in-app updater downloads and silent-installs it too.
# Usage: .\build_exe.ps1
# Requires Inno Setup (free, one-time): https://jrsoftware.org/isdl.php

# Note: deliberately NOT using $ErrorActionPreference = "Stop" — with it set,
# PowerShell 5.1 treats ANY stderr output from a native exe (e.g. pip's
# harmless "new version available" notice) as a terminating error even when
# the exe exits 0. Exit codes are checked explicitly after each step instead.

$version = (python -c "import sys; sys.path.insert(0, 'translator'); from app.version import APP_VERSION; print(APP_VERSION)").Trim()
Write-Host "Building Dubify AI v$version..."

pip install --quiet pyinstaller pyinstaller-hooks-contrib
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: pip install failed."; exit 1 }

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

python -m PyInstaller dubify.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: PyInstaller build failed."; exit 1 }

# On machines where python3.dll is installed as a symlink alias for
# python31X.dll (some Python installer/py-launcher setups do this, e.g. when
# multiple Python versions coexist), PyInstaller resolves the symlink and
# copies its full content as a SEPARATE file. That leaves two independent
# copies of the CPython runtime loaded under two DLL names in one process —
# guaranteed to access-violate (0xC0000005) the moment any abi3/stable-ABI
# extension (PySide6/shiboken6) touches python3.dll. Re-link it as a hardlink
# to python313.dll so Windows treats both names as the same loaded module.
$internalDir = "dist\DubifyAI\_internal"
$python3Dll = Join-Path $internalDir "python3.dll"
$python313Dll = Join-Path $internalDir "python313.dll"
if ((Test-Path $python3Dll) -and (Test-Path $python313Dll)) {
    Remove-Item $python3Dll -Force
    New-Item -ItemType HardLink -Path $python3Dll -Target $python313Dll | Out-Null
    Write-Host "Fixed up python3.dll (hardlinked to python313.dll to prevent duplicate-runtime crash)."
}

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
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Inno Setup build failed."; exit 1 }

$setupName = "dist\DubifyAI-Setup-v$version.exe"
Write-Host ""
Write-Host "Installer ready: $setupName"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Bump APP_VERSION in translator/app/version.py for the NEXT release (not this one)."
Write-Host "  2. On GitHub -> Releases -> Draft a new release -> tag 'v$version' -> upload $setupName as the ONLY asset."
Write-Host "  3. Publish. Friends running an older version see the Update button next launch; clicking it"
Write-Host "     downloads this same Setup.exe and silent-installs it over the old version, then restarts."
