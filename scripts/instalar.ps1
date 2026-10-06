$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Instale Python 3 para executar o assistente." }
& $python.Source (Join-Path $root "scripts/instalar.py") @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
