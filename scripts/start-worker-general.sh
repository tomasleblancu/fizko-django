#!/bin/bash

echo "⚙️ Iniciando Celery Worker General..."

# Esperar a que Redis y la DB estén disponibles
echo "⏳ Esperando servicios..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

echo "✅ Servicios listos, iniciando worker general..."

# Iniciar worker de Celery para colas generales
exec celery -A fizko_django worker \
    --loglevel=info \
    --queues=whatsapp,default,forms,analytics,notifications \
    --concurrency=3 \
    --hostname=general_worker@%h \
    --without-gossip \
    --without-mingle \
    --without-heartbeat