#!/bin/bash

echo "⏰ Iniciando Celery Beat..."

# Esperar a que Redis y la DB estén disponibles
echo "⏳ Esperando servicios..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

# Esperar un poco más para asegurar que la DB esté completamente lista
sleep 5

# Aplicar migraciones de django-celery-beat si es necesario
echo "🔄 Verificando migraciones de Celery Beat..."
python manage.py migrate django_celery_beat --noinput || echo "❌ Error en migraciones, continuando..."

echo "✅ Servicios listos, iniciando Celery Beat..."

# Limpiar archivos de lock previos si existen
rm -f celerybeat.pid || true

# Iniciar Celery Beat para tareas programadas
exec celery -A fizko_django beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --pidfile=/tmp/celerybeat.pid \
    --detach=False