# Usamos una imagen de Python ligera
FROM python:3.11-slim

# Instalamos compiladores de C++ (necesarios para validar código de ESCOM)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalamos las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El comando por defecto será no hacer nada (para que tú mandes los comandos)
CMD ["bash"]