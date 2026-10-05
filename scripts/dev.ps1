<#
  FOGROOM developer commands for Windows PowerShell (mirrors the Makefile).
  Usage:  ./scripts/dev.ps1 <target>
  Targets: setup, dev, dev-api, dev-web, migrate, seed, reset-db, test, test-api,
           test-web, e2e, lint, docker-up, docker-down
#>
param([Parameter(Position = 0)][string]$Target = "help")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Api = Join-Path $Root "apps/api"
$Py = Join-Path $Api ".venv/Scripts/python.exe"

function Invoke-Checked([scriptblock]$Block) {
  & $Block
  if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}

function In-Api([scriptblock]$Block) {
  Push-Location $Api
  try { Invoke-Checked $Block } finally { Pop-Location }
}

switch ($Target) {
  "setup" {
    if (-not (Test-Path (Join-Path $Root ".env"))) { Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env") }
    if (-not (Test-Path $Py)) { Invoke-Checked { python -m venv (Join-Path $Api ".venv") } }
    Invoke-Checked { & $Py -m pip install --upgrade pip }
    Invoke-Checked { & $Py -m pip install -e "$Api[dev]" }
    Push-Location $Root; try { Invoke-Checked { pnpm install } } finally { Pop-Location }
    Push-Location $Root; try { Invoke-Checked { docker compose up -d --wait postgres redis } } finally { Pop-Location }
    In-Api { & $Py -m alembic upgrade head }
    In-Api { & $Py -m app.seed }
  }
  "migrate" { In-Api { & $Py -m alembic upgrade head } }
  "seed" { In-Api { & $Py -m app.seed } }
  "reset-db" {
    In-Api { & $Py -m alembic downgrade base }
    In-Api { & $Py -m alembic upgrade head }
    In-Api { & $Py -m app.seed }
  }
  "dev-api" {
    $port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
    In-Api { & $Py -m uvicorn app.main:app --reload --port $port }
  }
  "dev-web" { Push-Location $Root; try { Invoke-Checked { pnpm --filter @fogroom/web dev } } finally { Pop-Location } }
  "dev" {
    Push-Location $Root; try { Invoke-Checked { docker compose up -d --wait postgres redis } } finally { Pop-Location }
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$PSCommandPath' dev-api"
    & $PSCommandPath dev-web
  }
  "test-api" { In-Api { & $Py -m pytest -q } }
  "test-web" { Push-Location $Root; try { Invoke-Checked { pnpm --filter @fogroom/web test } } finally { Pop-Location } }
  "test" { & $PSCommandPath test-api; & $PSCommandPath test-web }
  "e2e" { Push-Location $Root; try { Invoke-Checked { pnpm --filter @fogroom/web e2e } } finally { Pop-Location } }
  "lint" {
    In-Api { & $Py -m ruff check . }
    In-Api { & $Py -m ruff format --check . }
    In-Api { & $Py -m mypy app }
    Push-Location $Root
    try {
      Invoke-Checked { pnpm --filter @fogroom/web lint }
      Invoke-Checked { pnpm --filter @fogroom/web typecheck }
    } finally { Pop-Location }
  }
  "docker-up" { Push-Location $Root; try { Invoke-Checked { docker compose up -d --build } } finally { Pop-Location } }
  "docker-down" { Push-Location $Root; try { Invoke-Checked { docker compose down } } finally { Pop-Location } }
  default {
    Write-Host "Targets: setup, dev, dev-api, dev-web, migrate, seed, reset-db, test, test-api, test-web, e2e, lint, docker-up, docker-down"
  }
}
