#!/bin/bash

echo "⏰ Iniciando Celery Beat (Debug)..."

# Verificar conexión a Redis
echo "🔍 Verificando Redis..."
python -c "
import redis
from decouple import config
redis_url = config('REDIS_URL', default='redis://localhost:6379')
r = redis.from_url(redis_url)
print('Redis ping:', r.ping())
" || echo "❌ Error conectando a Redis"

# Verificar conexión a DB
echo "🔍 Verificando DB..."
python manage.py check --database default || echo "❌ Error verificando DB"

# Esperar servicios
echo "⏳ Esperando servicios..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

# Esperar más tiempo
sleep 10

# Verificar migraciones
echo "🔄 Verificando migraciones..."
python manage.py showmigrations django_celery_beat

# Aplicar migraciones
echo "🔄 Aplicando migraciones de Celery Beat..."
python manage.py migrate django_celery_beat --noinput || echo "❌ Error en migraciones"

echo "✅ Servicios listos, iniciando Celery Beat..."

# Limpiar archivos de lock
rm -f celerybeat.pid /tmp/celerybeat.pid || true

# Mostrar configuración
echo "📋 Configuración Celery:"
python -c "
from fizko_django import settings
print('CELERY_BROKER_URL:', getattr(settings, 'CELERY_BROKER_URL', 'Not set'))
print('CELERY_BEAT_SCHEDULER:', getattr(settings, 'CELERY_BEAT_SCHEDULER', 'Not set'))
"

# Iniciar con verbose logging
exec celery -A fizko_django beat \
    --loglevel=debug \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --pidfile=/tmp/celerybeat.pid \
    --detach=False