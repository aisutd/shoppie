$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create the project virtual environment first; expected $python"
}

& $python -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing. Install it with: $python -m pip install pyinstaller"
}

& $python -m PyInstaller --noconfirm --clean --onefile --console `
    --name ShoppieUploader `
    --distpath $PSScriptRoot `
    --workpath (Join-Path $PSScriptRoot "build\work") `
    --specpath (Join-Path $PSScriptRoot "build") `
    (Join-Path $PSScriptRoot "interactive_upload.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built $PSScriptRoot\ShoppieUploader.exe"
Write-Host "The existing .env stays beside the executable and is not bundled into it."
