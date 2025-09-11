#!/bin/bash

echo "🚀 Iniciando servicio web de Fizko..."

# Esperar a que la base de datos esté disponible
echo "⏳ Esperando base de datos..."
python manage.py wait_for_db || echo "❌ Error esperando DB, continuando..."

# Ejecutar migraciones
echo "📊 Ejecutando migraciones..."
python manage.py migrate --noinput

# Recopilar archivos estáticos
echo "📁 Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# Crear superusuario si no existe (opcional)
echo "👤 Verificando superusuario..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('No superuser found, remember to create one manually')
" || echo "ℹ️  Superuser check skipped"

echo "✅ Configuración completa, iniciando Gunicorn..."

# Iniciar Gunicorn con configuración optimizada para Railway
exec gunicorn fizko_django.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 4 \
    --worker-class gthread \
    --threads 2 \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 120 \
    --keep-alive 5 \
    --preload \
    --log-level info \
    --access-logfile - \
    --error-logfile -