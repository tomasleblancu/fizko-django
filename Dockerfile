FROM python:3.11-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    chromium \
    chromium-driver \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements e instalar dependencias Python
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/railway.txt

# Copiar código fuente
COPY . /app/

# Railway maneja usuarios automáticamente
# Crear directorios necesarios y permisos
RUN mkdir -p /app/static /app/media /app/logs \
    && chmod +x /app/scripts/*.sh

# Colectar archivos estáticos se hace en runtime
# RUN python manage.py collectstatic --noinput || true

# Railway maneja puertos dinámicamente
EXPOSE 8000

# Comando por defecto optimizado para Railway
CMD ["./scripts/start-web.sh"]