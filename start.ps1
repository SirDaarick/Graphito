# Script de arranque rápido para Graphito (Windows)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     INICIANDO GRAPHITO CON DOCKER      " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Verificar .env
if (-not (Test-Path ".env")) {
    Write-Host "[1/2] Creando archivo .env desde .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
} else {
    Write-Host "[1/2] Archivo .env detectado." -ForegroundColor Green
}

# 2. Levantar servicios
Write-Host "[2/2] Levantando contenedores de Docker (Frontend, Backend, Postgres, Chroma)..." -ForegroundColor Green
docker compose up --build
