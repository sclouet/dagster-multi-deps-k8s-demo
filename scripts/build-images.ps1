<#
.SYNOPSIS
    Construit les images Docker des 3 outils + de l'orchestrateur.
.NOTES
    Necessite Docker Desktop.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker n'est pas disponible sur cette machine. Installe Docker Desktop puis relance ce script." -ForegroundColor Yellow
    exit 1
}

Write-Host "Construction de dagster-demo/tool-ingest:local ..." -ForegroundColor Cyan
docker build -t dagster-demo/tool-ingest:local "$root/tools/tool_ingest"

Write-Host "Construction de dagster-demo/tool-enrich:local ..." -ForegroundColor Cyan
docker build -t dagster-demo/tool-enrich:local "$root/tools/tool_enrich"

Write-Host "Construction de dagster-demo/tool-score:local ..." -ForegroundColor Cyan
docker build -t dagster-demo/tool-score:local "$root/tools/tool_score"

Write-Host "Construction de dagster-demo/orchestrator:local ..." -ForegroundColor Cyan
docker build -t dagster-demo/orchestrator:local -f "$root/orchestrator/Dockerfile" "$root"

Write-Host "`nImages construites localement." -ForegroundColor Green
Write-Host "Sur minikube, charge-les dans le cluster avant le deploiement :" -ForegroundColor Cyan
Write-Host "  minikube image load dagster-demo/tool-ingest:local"
Write-Host "  minikube image load dagster-demo/tool-enrich:local"
Write-Host "  minikube image load dagster-demo/tool-score:local"
Write-Host "Sur kind :" -ForegroundColor Cyan
Write-Host "  kind load docker-image dagster-demo/tool-ingest:local"
Write-Host "  kind load docker-image dagster-demo/tool-enrich:local"
Write-Host "  kind load docker-image dagster-demo/tool-score:local"
