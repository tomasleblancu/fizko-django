#!/bin/bash

# Script para iniciar desarrollo con ngrok automáticamente
# Uso: ./scripts/start_dev_with_ngrok.sh

echo "🚀 Iniciando Fizko en modo desarrollo con ngrok..."

# Levantar servicios en desarrollo (incluyendo ngrok)
echo "📦 Levantando servicios..."
docker-compose --profile development up -d

# Esperar a que ngrok se inicialice
echo "⏳ Esperando que ngrok se inicialice..."
sleep 8

# Obtener y mostrar la URL
echo ""
echo "🌐 Obteniendo URL pública..."
./scripts/get_ngrok_url.sh

echo ""
echo "✅ Servicios disponibles:"
echo "   🐘 Django: http://localhost:8000"
echo "   🌸 PostgreSQL: localhost:5432"
echo "   🔴 Redis: localhost:6379"
echo "   🌺 Flower (Celery): http://localhost:5555"
echo "   📊 ngrok Dashboard: http://localhost:4040"
echo ""
echo "📱 Para configurar webhook en Kapso:"
echo "   1. Ve a tu dashboard de Kapso"
echo "   2. Configura webhook con la URL mostrada arriba"
echo "   3. Selecciona eventos: message.received, message.sent, etc."
echo ""
echo "🔧 Comandos útiles:"
echo "   docker-compose logs -f              # Ver todos los logs"
echo "   docker-compose logs -f ngrok        # Solo logs de ngrok"
echo "   ./scripts/get_ngrok_url.sh          # Obtener URL nuevamente"
echo "   docker-compose down                 # Parar todo"
echo ""
echo "🎉 ¡Listo para desarrollo!"