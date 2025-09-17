FROM python:3.12-slim

# Sistema base
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libpq5 libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Evitar archivos .pyc y forzar stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Requisitos
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copiar código
COPY . /app

# Permisos y entrypoint
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
