#!/bin/bash

echo "⏰ Iniciando Celery Beat con Health Server..."

# Iniciar servidor de health primero
echo "🩺 Iniciando health server..."
python3 ./scripts/health-server.py &
HEALTH_PID=$!

# Esperar que el health server esté listo
sleep 5

# Verificar health server
if curl -f http://localhost:8080/health/ > /dev/null 2>&1; then
    echo "✅ Health endpoint funcionando"
else
    echo "❌ Health endpoint no responde, continuando..."
fi

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
rm -f celerybeat.pid /tmp/celerybeat.pid || true

# Crear handler para limpieza al salir
cleanup() {
    echo "🧹 Limpiando procesos..."
    kill $HEALTH_PID 2>/dev/null || true
    rm -f /tmp/celerybeat.pid || true
    exit 0
}
trap cleanup EXIT INT TERM

# Iniciar Celery Beat para tareas programadas
exec celery -A fizko_django beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --pidfile=/tmp/celerybeat.pid