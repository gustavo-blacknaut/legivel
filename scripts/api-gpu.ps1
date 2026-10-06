param(
    [string]$Python = "",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = Join-Path $root "apps\api"

if (-not $Python) {
    foreach ($candidate in @(".venv\Scripts\python.exe", ".venv-gpu\Scripts\python.exe")) {
        $path = Join-Path $root $candidate
        if (Test-Path $path) { $Python = $path; break }
    }
}
if (-not $Python -or -not (Test-Path $Python)) {
    throw "Ambiente Python não encontrado. Crie com: python -m venv .venv e pip install -e `"apps/api[gpu-directml,tesseract]`""
}

$values = @{}
foreach ($line in Get-Content (Join-Path $root ".env")) {
    if ($line -match '^\s*([A-Z0-9_]+)=(.*)$') { $values[$Matches[1]] = $Matches[2] }
}
$secretFiles = @{
    "POSTGRES_PASSWORD" = "postgres_password"
    "LEGIVEL_SECRET_KEY" = "secret_key"
    "LEGIVEL_ENCRYPTION_KEY" = "encryption_key"
}
foreach ($entry in $secretFiles.GetEnumerator()) {
    $path = Join-Path $root "secrets\$($entry.Value)"
    if (-not $values[$entry.Key] -and (Test-Path $path)) { $values[$entry.Key] = (Get-Content -Raw $path).Trim() }
}
foreach ($required in @("POSTGRES_PASSWORD", "LEGIVEL_SECRET_KEY")) {
    if (-not $values[$required]) { throw "$required não está definido no .env nem em secrets\$($secretFiles[$required])" }
}
foreach ($entry in $values.GetEnumerator()) {
    if ($entry.Key.StartsWith("LEGIVEL_")) { Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value }
}

$user = if ($values["POSTGRES_USER"]) { $values["POSTGRES_USER"] } else { "legivel" }
$database = if ($values["POSTGRES_DB"]) { $values["POSTGRES_DB"] } else { "legivel" }
$pgPort = if ($values["POSTGRES_HOST_PORT"]) { $values["POSTGRES_HOST_PORT"] } else { "5432" }
$password = [uri]::EscapeDataString($values["POSTGRES_PASSWORD"])
$env:LEGIVEL_DATABASE_URL = "postgresql+psycopg://${user}:${password}@127.0.0.1:${pgPort}/${database}"
$env:LEGIVEL_STORAGE_DIR = Join-Path $root "storage"
$env:LEGIVEL_OCR_MODEL_DIR = Join-Path $api "models"
$env:LEGIVEL_OCR_DEVICE = "auto"

Push-Location $api
try {
    & $Python -m legivel.cli check-config
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m legivel.cli download-models
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m legivel.cli reencrypt --if-needed
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m uvicorn legivel.main:create_app --factory --host 127.0.0.1 --port $Port --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log
}
finally {
    Pop-Location
}
