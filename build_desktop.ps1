# Build CC Studio Windows onedir package (v0.2.1)
#   .\build_desktop.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing PyInstaller + PySide6..."
python -m pip install -q -r requirements-desktop.txt pyinstaller

Write-Host "Cleaning previous build..."
Remove-Item -Recurse -Force dist\CCStudio -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force build\CCStudio -ErrorAction SilentlyContinue

Write-Host "Building..."
python -m PyInstaller --noconfirm --clean CCStudio.spec

$exe = Join-Path $PSScriptRoot "dist\CCStudio\CCStudio.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Build failed: $exe not found"
    exit 1
}

$size = (Get-ChildItem -Recurse dist\CCStudio | Measure-Object -Property Length -Sum).Sum
Write-Host "OK: $exe"
Write-Host ("Bundle size: {0:N1} MB" -f ($size / 1MB))
