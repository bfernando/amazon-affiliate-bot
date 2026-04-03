$ErrorActionPreference = "Stop"

$repo = "C:\Projects\amazon-affiliate-bot"
Set-Location $repo

# Prefer venv python if present, otherwise use system python.
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  $python = "python"
}

& $python "main.py" --post --mode best
