param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& $Python -m pip install --target vendor -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '依存関係の準備に失敗しました' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'vendor'
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name SimplePDF --collect-all tkinterdnd2 --exclude-module matplotlib --exclude-module scipy --exclude-module pandas --exclude-module IPython --exclude-module pytest app.py
if ($LASTEXITCODE -ne 0) { throw 'ビルドに失敗しました' }
