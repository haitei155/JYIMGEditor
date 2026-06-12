$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "JYIMGEditor" `
  "main.py"

Copy-Item -LiteralPath "config.ini" -Destination "dist\config.ini" -Force
Get-ChildItem -LiteralPath "dist" -Filter "*v0.1.exe" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "Built: dist/JYIMGEditor.exe"
