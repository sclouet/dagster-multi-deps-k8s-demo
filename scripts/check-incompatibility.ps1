<#
.SYNOPSIS
    Prouve que les stacks de tool_enrich et tool_score sont reellement
    incompatibles : tente de les installer ensemble, dans UN SEUL
    environnement Python 3.11 (qui a des wheels precompiles pour les deux
    versions de numpy en jeu, pour un conflit net sans bruit de compilation),
    via une image python:3.11-slim jetable.
.NOTES
    Necessite Docker Desktop (docker doit repondre a `docker version`).
    C'est precisement le probleme que les code locations Dagster isolees
    (un environnement/une image par outil) permettent de contourner.
#>

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker n'est pas disponible sur cette machine. Installe Docker Desktop puis relance ce script." -ForegroundColor Yellow
    exit 1
}

Write-Host "Tentative d'installation conjointe de :" -ForegroundColor Cyan
Write-Host "  - tool_enrich : pandas==2.2.2, numpy>=1.26,<2 (pin explicite, voir pyproject.toml)"
Write-Host "  - tool_score  : numpy==1.23.5, scikit-learn==1.0.2 (casse avec numpy>=1.24)"
Write-Host "...dans un seul environnement python:3.11-slim." -ForegroundColor Cyan

$requirements = @"
pandas==2.2.2
numpy>=1.26,<2
pydantic>=2,<3
numpy==1.23.5
scikit-learn==1.0.2
"@

$tempFile = New-TemporaryFile
Set-Content -Path $tempFile -Value $requirements -Encoding utf8

docker run --rm -v "${tempFile}:/requirements.txt:ro" python:3.11-slim `
    pip install --no-cache-dir -r /requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nConflit confirme : pip refuse de resoudre ces deux stacks ensemble." -ForegroundColor Green
    Write-Host "C'est exactement le probleme que les code locations Dagster isolees resolvent." -ForegroundColor Green
} else {
    Write-Host "`nInstallation reussie (inattendu) - revoir les versions pinnees dans les pyproject.toml des outils." -ForegroundColor Red
}

Remove-Item $tempFile -Force
