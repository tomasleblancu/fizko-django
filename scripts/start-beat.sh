#!/bin/bash

echo "⏰ Iniciando Celery Beat..."

# Esperar a que Redis y la DB estén disponibles
echo "⏳ Esperando servicios..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

echo "✅ Servicios listos, iniciando Celery Beat..."

# Iniciar Celery Beat para tareas programadas
exec celery -A fizko_django beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler