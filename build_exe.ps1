# Builds the Windows exe (onedir) and zips it for a GitHub Release asset.
# Usage: .\build_exe.ps1

$ErrorActionPreference = "Stop"

$version = (python -c "import sys; sys.path.insert(0, 'translator'); from app.version import APP_VERSION; print(APP_VERSION)").Trim()
Write-Host "Building Dubify AI v$version..."

pip install --quiet pyinstaller pyinstaller-hooks-contrib

if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }

pyinstaller dubify.spec --noconfirm --clean

$zipName = "dist\DubifyAI-v$version-win64.zip"
if (Test-Path $zipName) { Remove-Item $zipName -Force }
Compress-Archive -Path "dist\DubifyAI\*" -DestinationPath $zipName

Write-Host ""
Write-Host "Build done: dist\DubifyAI\DubifyAI.exe"
Write-Host "Release asset ready: $zipName"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Bump APP_VERSION in translator/app/version.py for the NEXT release (not this one)."
Write-Host "  2. On GitHub -> Releases -> Draft a new release -> tag 'v$version' -> upload $zipName as an asset."
Write-Host "  3. Publish. Friends running an older version will see the Update button next launch."
