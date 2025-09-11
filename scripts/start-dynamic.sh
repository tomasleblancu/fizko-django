#!/bin/bash

# Script dinámico que ejecuta el comando correcto basado en START_COMMAND
# Si no está definida, usa start-web.sh por defecto

if [ -n "$START_COMMAND" ]; then
    echo "🚀 Ejecutando comando personalizado: $START_COMMAND"
    
    # Los workers de Celery necesitan un endpoint dummy para Railway healthcheck
    if [[ "$START_COMMAND" == *"worker"* ]] || [[ "$START_COMMAND" == *"beat"* ]]; then
        echo "📡 Servicio Celery detectado - iniciando endpoint dummy"
        
        # Iniciar servidor HTTP simple en background para healthcheck
        python3 -c "
import http.server
import socketserver
import threading
import time

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Silenciar logs

def start_server():
    try:
        with socketserver.TCPServer(('0.0.0.0', 8080), HealthHandler) as httpd:
            httpd.serve_forever()
    except:
        pass

# Iniciar servidor en background
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
print('Health endpoint iniciado en puerto 8080')
" &
        
        # Esperar un poco para que el servidor inicie
        sleep 2
    fi
    
    exec $START_COMMAND
else
    echo "🌐 Ejecutando comando por defecto: ./scripts/start-web.sh"
    exec ./scripts/start-web.sh
fi