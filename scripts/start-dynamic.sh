#!/bin/bash

# Script dinámico que ejecuta el comando correcto basado en START_COMMAND
# Si no está definida, usa start-web.sh por defecto

if [ -n "$START_COMMAND" ]; then
    echo "🚀 Ejecutando comando personalizado: $START_COMMAND"
    exec $START_COMMAND
else
    echo "🌐 Ejecutando comando por defecto: ./scripts/start-web.sh"
    exec ./scripts/start-web.sh
fi