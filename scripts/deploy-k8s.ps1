<#
.SYNOPSIS
    Deploie MinIO + le chart Helm officiel dagster/dagster sur le cluster
    k8s courant (minikube/kind). A lancer apres build-images.ps1 et apres
    avoir charge les images dans le cluster (voir la sortie de ce script).
.NOTES
    Necessite kubectl et helm, configures sur le bon contexte de cluster.
#>

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "kubectl introuvable. Installe kubectl puis relance ce script." -ForegroundColor Yellow
    exit 1
}
if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Host "helm introuvable. Installe Helm puis relance ce script." -ForegroundColor Yellow
    exit 1
}

Write-Host "Contexte kubectl courant :" -ForegroundColor Cyan
kubectl config current-context

Write-Host "`nDeploiement de MinIO (stockage partage)..." -ForegroundColor Cyan
kubectl apply -f "$root/k8s/minio.yaml"

Write-Host "`nAjout/maj du repo Helm Dagster..." -ForegroundColor Cyan
helm repo add dagster https://dagster-io.github.io/helm | Out-Null
helm repo update | Out-Null

Write-Host "`nInstallation/mise a jour du chart Dagster (webserver + daemon + les 3 outils)..." -ForegroundColor Cyan
helm upgrade --install demo dagster/dagster `
    -f "$root/k8s/helm-values.yaml" `
    -f "$root/k8s/dagster-instance-values.yaml"

Write-Host "`nDeploiement lance. Pour suivre les pods :" -ForegroundColor Green
Write-Host "  kubectl get pods -w"
Write-Host "Pour acceder a l'UI Dagster une fois les pods 'Running' :" -ForegroundColor Green
Write-Host "  kubectl port-forward svc/demo-dagster-webserver 3000:80"
Write-Host "  puis ouvrir http://localhost:3000"
