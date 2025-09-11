#!/bin/bash

# Script para obtener la URL pública de ngrok
# Uso: ./scripts/get_ngrok_url.sh

echo "🔍 Obteniendo URL pública de ngrok..."

# Verificar si el contenedor de ngrok está corriendo
if ! docker-compose ps ngrok | grep -q "Up"; then
    echo "❌ El contenedor de ngrok no está corriendo."
    echo "💡 Ejecuta: docker-compose --profile development up -d ngrok"
    exit 1
fi

# Esperar un momento para que ngrok se inicialice
sleep 2

# Obtener la URL desde la API de ngrok
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url' 2>/dev/null)

# Si tienes dominio fijo configurado, usar ese
if [ -f ".env" ] && grep -q "NGROK_FIXED_URL" .env; then
    FIXED_URL=$(grep "NGROK_FIXED_URL" .env | cut -d'=' -f2)
    if [ "$FIXED_URL" != "" ]; then
        NGROK_URL="https://$FIXED_URL"
    fi
fi

# Fallback a dominio fijo por defecto
if [ "$NGROK_URL" = "null" ] || [ "$NGROK_URL" = "" ]; then
    NGROK_URL="https://balanced-elk-awaited.ngrok-free.app"
    echo "🔧 Usando dominio fijo configurado"
fi

if [ "$NGROK_URL" != "null" ] && [ "$NGROK_URL" != "" ]; then
    echo "✅ URL pública de ngrok: $NGROK_URL"
    echo "📱 Webhook URL para Kapso: ${NGROK_URL}/api/v1/whatsapp/webhook/"
    echo "🌐 Dashboard de ngrok: http://localhost:4040"
    echo ""
    echo "📋 Para copiar al portapapeles (macOS):"
    echo "   echo '${NGROK_URL}/api/v1/whatsapp/webhook/' | pbcopy"
    echo ""
    echo "🔧 Para configurar en Kapso, usa esta URL:"
    echo "   ${NGROK_URL}/api/v1/whatsapp/webhook/"
else
    echo "❌ No se pudo obtener la URL de ngrok."
    echo "🔍 Verifica los logs: docker-compose logs ngrok"
    echo "🌐 O visita: http://localhost:4040"
fi