#!/bin/bash

echo "🤖 Iniciando Celery Worker SII..."

# Esperar a que Redis y la DB estén disponibles
echo "⏳ Esperando servicios..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

echo "✅ Servicios listos, iniciando worker SII..."

# Iniciar worker de Celery para cola SII
exec celery -A fizko_django worker \
    --loglevel=info \
    --queues=sii \
    --concurrency=2 \
    --hostname=sii_worker@%h \
    --without-gossip \
    --without-mingle \
    --without-heartbeat