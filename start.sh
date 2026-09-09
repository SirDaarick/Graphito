#!/usr/bin/env bash
set -e

echo "========================================"
echo "     INICIANDO GRAPHITO CON DOCKER      "
echo "========================================"

# 1. Verificar .env
if [ ! -f ".env" ]; then
    echo "[1/2] Creando archivo .env desde .env.example..."
    cp .env.example .env
else
    echo "[1/2] Archivo .env detectado."
fi

# 2. Levantar servicios
echo "[2/2] Levantando contenedores de Docker..."
docker compose up --build
