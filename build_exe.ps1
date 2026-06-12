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
python -c "from pathlib import Path; target='\u91d1\u5eb8\u7fa4\u4fa0\u4f20\u8d34\u56fe\u8d44\u6e90\u7f16\u8f91\u5668v0.1.exe'; d=Path('dist'); p=d/'JYIMGEditor.exe'; q=d/target; [x.unlink() for x in d.glob('*v0.1.exe') if x.name != target]; ok=True
try:
    q.unlink(missing_ok=True)
    p.rename(q)
except PermissionError:
    ok=False
    print('Built:', p)
    print('Note: close the old Chinese-named exe and rerun build_exe.ps1 to replace:', q)
if ok:
    print('Built:', q)"
Write-Host "Built: dist/JYIMGEditor v0.1"
