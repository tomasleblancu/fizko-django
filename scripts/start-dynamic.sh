#!/bin/bash

# Script dinámico que ejecuta el comando correcto basado en START_COMMAND
# Si no está definida, usa start-web.sh por defecto

if [ -n "$START_COMMAND" ]; then
    echo "🚀 Ejecutando comando personalizado: $START_COMMAND"
    
    # Los workers de Celery necesitan un endpoint dummy para Railway healthcheck
    if [[ "$START_COMMAND" == *"worker"* ]] || [[ "$START_COMMAND" == *"beat"* ]]; then
        echo "📡 Servicio Celery detectado - iniciando endpoint dummy"
        
        # Iniciar servidor de health en background
        python3 ./scripts/health-server.py &
        HEALTH_PID=$!
        
        # Esperar un poco para que el servidor inicie
        sleep 3
        
        # Verificar que el servidor esté funcionando
        if curl -f http://localhost:8080/health/ > /dev/null 2>&1; then
            echo "✅ Health endpoint funcionando"
        else
            echo "❌ Health endpoint no responde"
        fi
    fi
    
    exec $START_COMMAND
else
    echo "🌐 Ejecutando comando por defecto: ./scripts/start-web.sh"
    exec ./scripts/start-web.sh
fi