#!/usr/bin/env python3
"""
Servidor HTTP simple para healthchecks de servicios Celery
"""
import http.server
import socketserver
import sys
import os

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def do_HEAD(self):
        if self.path == '/health/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Silenciar logs HTTP para no contaminar logs de Celery
        pass

def start_health_server(port=8080):
    """Inicia el servidor de health en el puerto especificado"""
    try:
        with socketserver.TCPServer(("0.0.0.0", port), HealthHandler) as httpd:
            print(f"🩺 Health server iniciado en puerto {port}")
            httpd.serve_forever()
    except OSError as e:
        print(f"❌ Error iniciando health server en puerto {port}: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("🛑 Health server detenido")
        sys.exit(0)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    start_health_server(port)