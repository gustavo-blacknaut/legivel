$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$secretsDir = Join-Path $root "secrets"
$envFile = Join-Path $root ".env"

$values = @{}
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*([A-Z0-9_]+)=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim().Trim('"', "'") }
    }
}

function New-RandomBytes([int]$count) {
    $bytes = New-Object byte[] $count
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return $bytes
}

function New-RandomPassword { return ([Convert]::ToBase64String((New-RandomBytes 33)) -replace '[/+=]', '') }

function New-RandomKey { return ([Convert]::ToBase64String((New-RandomBytes 32)) -replace '\+', '-' -replace '/', '_') }

function Write-Secret([string]$name, [string]$variable, [scriptblock]$generator) {
    $target = Join-Path $secretsDir $name
    if ((Test-Path $target) -and (Get-Item $target).Length -gt 0) {
        Write-Output "${name}: mantido"
        return
    }
    if ($variable -and $values[$variable]) {
        $value = $values[$variable]
        $origin = "copiado de $variable no .env"
    }
    else {
        $value = & $generator
        $origin = "gerado"
    }
    [System.IO.File]::WriteAllText($target, $value)
    Write-Output "${name}: $origin"
}

New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null
Write-Secret "postgres_password" "POSTGRES_PASSWORD" { New-RandomPassword }
Write-Secret "database_app_password" "" { New-RandomPassword }
Write-Secret "secret_key" "LEGIVEL_SECRET_KEY" { New-RandomKey }
Write-Secret "encryption_key" "LEGIVEL_ENCRYPTION_KEY" { New-RandomKey }
Write-Secret "backup_passphrase" "" { New-RandomPassword }
Write-Output "Segredos em $secretsDir. Guarde uma cópia de encryption_key e de backup_passphrase fora do servidor: sem elas as imagens e os backups não podem ser lidos."
