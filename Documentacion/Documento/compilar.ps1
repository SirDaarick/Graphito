# Script de compilación rápida para Graphito
Set-Location -Path $PSScriptRoot
Write-Host "==> Compilando documento LaTeX con Tectonic..." -ForegroundColor Cyan
tectonic main.tex
if ($LASTEXITCODE -eq 0) {
    Write-Host "==> Compilación exitosa: main.pdf generado correctamente." -ForegroundColor Green
} else {
    Write-Host "==> Error durante la compilación." -ForegroundColor Red
}
