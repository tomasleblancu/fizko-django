#!/bin/bash

echo "📄 Iniciando Celery Worker Documentos..."

# Esperar a que Redis y la DB estén disponibles
echo "⏳ Esperando servicios..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

echo "✅ Servicios listos, iniciando worker documentos..."

# Iniciar worker de Celery para cola de documentos
exec celery -A fizko_django worker \
    --loglevel=info \
    --queues=documents \
    --concurrency=4 \
    --hostname=documents_worker@%h \
    --without-gossip \
    --without-mingle \
    --without-heartbeat