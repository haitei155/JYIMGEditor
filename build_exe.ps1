$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "JYIMGEditor" `
  --icon "assets\JYIMGEditor.ico" `
  --add-data "assets;assets" `
  --exclude-module "numpy" `
  --exclude-module "scipy" `
  --exclude-module "pandas" `
  --exclude-module "matplotlib" `
  --exclude-module "IPython" `
  --exclude-module "notebook" `
  --exclude-module "jupyter" `
  --exclude-module "pytest" `
  --exclude-module "pygame" `
  --exclude-module "setuptools" `
  --exclude-module "pkg_resources" `
  --exclude-module "packaging" `
  --exclude-module "platformdirs" `
  --exclude-module "PIL.ImageQt" `
  --exclude-module "PIL.ImageShow" `
  "main.py"

Copy-Item -LiteralPath "config.ini" -Destination "dist\config.ini" -Force
Get-ChildItem -LiteralPath "dist" -Filter "*v0.1.exe" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "Built: dist/JYIMGEditor.exe"
