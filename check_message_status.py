#!/usr/bin/env python
"""
Verifica el estado de los últimos mensajes enviados
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fizko_django.settings')
django.setup()

def check_message_status():
    """Verifica el estado de los mensajes recientes"""
    import requests
    from django.conf import settings
    import logging
    from datetime import datetime

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    api_token = getattr(settings, 'KAPSO_API_TOKEN')
    base_url = getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')

    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json'
    }

    target_phone = "56975389973"
    conversation_id = "c1c4c2b8-79ba-44eb-9dd5-5c834b3702c2"  # Del diagnóstico anterior

    print("\n" + "="*50)
    print("📱 VERIFICANDO ESTADO DE MENSAJES")
    print("="*50)

    try:
        # 1. Obtener mensajes de la conversación
        print(f"\n1️⃣ Mensajes en conversación {conversation_id}:")
        print("-" * 40)

        messages_response = requests.get(
            f'{base_url}/whatsapp_conversations/{conversation_id}/whatsapp_messages?limit=10',
            headers=headers,
            timeout=10
        )

        if messages_response.status_code == 200:
            messages_data = messages_response.json()
            messages = messages_data.get('data', [])

            print(f"✓ Total de mensajes recientes: {len(messages)}")

            if messages:
                print("\n📨 Mensajes recientes:")
                for i, msg in enumerate(messages[:5]):  # Últimos 5 mensajes
                    direction = "➡️ Enviado" if msg.get('direction') == 'outbound' else "⬅️ Recibido"
                    status = msg.get('status', 'unknown')
                    content = msg.get('content', '')[:80]
                    created = msg.get('created_at', 'N/A')
                    msg_id = msg.get('id', 'N/A')
                    whatsapp_id = msg.get('whatsapp_message_id', 'N/A')

                    print(f"\n   {i+1}. {direction} [{status}]")
                    print(f"      ID: {msg_id}")
                    print(f"      WhatsApp ID: {whatsapp_id}")
                    print(f"      Contenido: {content}...")
                    print(f"      Fecha: {created}")

                    # Obtener detalles específicos del mensaje
                    if msg.get('id'):
                        detail_response = requests.get(
                            f'{base_url}/whatsapp_messages/{msg["id"]}',
                            headers=headers,
                            timeout=5
                        )

                        if detail_response.status_code == 200:
                            detail_data = detail_response.json()
                            detail = detail_data.get('data', {})

                            error_msg = detail.get('error_message')
                            if error_msg:
                                print(f"      ❌ Error: {error_msg}")

                            delivery_status = detail.get('delivery_status')
                            if delivery_status:
                                print(f"      📲 Estado de entrega: {delivery_status}")

            else:
                print("❌ No se encontraron mensajes en la conversación")

        else:
            print(f"❌ Error obteniendo mensajes: {messages_response.status_code}")
            print(f"   Respuesta: {messages_response.text[:300]}")

        # 2. Verificar estado general de la conversación
        print(f"\n2️⃣ Estado de la conversación:")
        print("-" * 40)

        conv_response = requests.get(
            f'{base_url}/whatsapp_conversations/{conversation_id}',
            headers=headers,
            timeout=10
        )

        if conv_response.status_code == 200:
            conv_data = conv_response.json()
            conv = conv_data.get('data', {})

            print(f"   - Estado: {conv.get('status', 'N/A')}")
            print(f"   - Última actividad: {conv.get('last_message_at', 'N/A')}")
            print(f"   - Mensajes no leídos: {conv.get('unread_count', 0)}")
            print(f"   - Configuración WhatsApp: {conv.get('whatsapp_config_id', 'N/A')}")

            # 3. Información adicional si está disponible
            if conv.get('contact'):
                contact = conv['contact']
                print(f"   - Contacto: {contact.get('name', 'N/A')}")
                print(f"   - Teléfono verificado: {contact.get('phone_verified', 'N/A')}")

        # 4. Enviar un mensaje de prueba final
        print(f"\n3️⃣ Enviando mensaje final de verificación:")
        print("-" * 40)

        timestamp = datetime.now().strftime("%H:%M:%S")
        final_message = f"✅ Verificación final - {timestamp}\n\nSi recibes este mensaje, el sistema está funcionando correctamente. Por favor responde 'OK' para confirmar."

        final_payload = {
            'message': {
                'content': final_message,
                'message_type': 'text'
            }
        }

        final_response = requests.post(
            f'{base_url}/whatsapp_conversations/{conversation_id}/whatsapp_messages',
            headers=headers,
            json=final_payload,
            timeout=30
        )

        if final_response.status_code in [200, 201]:
            result = final_response.json()
            data = result.get('data', {})
            print(f"✅ MENSAJE FINAL ENVIADO")
            print(f"   - Message ID: {data.get('id')}")
            print(f"   - WhatsApp ID: {data.get('whatsapp_message_id')}")
            print(f"   - Estado inicial: {data.get('status')}")

            # Esperar un poco y verificar el estado
            print(f"\n   ⏳ Verificando estado después de 5 segundos...")
            import time
            time.sleep(5)

            if data.get('id'):
                status_check = requests.get(
                    f'{base_url}/whatsapp_messages/{data["id"]}',
                    headers=headers,
                    timeout=10
                )

                if status_check.status_code == 200:
                    status_data = status_check.json()
                    msg_detail = status_data.get('data', {})
                    final_status = msg_detail.get('status', 'unknown')

                    print(f"   📊 Estado final: {final_status}")

                    if final_status == 'sent':
                        print("   ✅ El mensaje fue enviado a WhatsApp")
                    elif final_status == 'delivered':
                        print("   ✅ El mensaje fue entregado al dispositivo")
                    elif final_status == 'failed':
                        print("   ❌ El mensaje falló")
                        error = msg_detail.get('error_message', 'Sin detalles')
                        print(f"   Error: {error}")

                    print(f"\n🔔 REVISA TU WHATSAPP AHORA")
                    print(f"   Si no recibes el mensaje, el problema puede ser:")
                    print(f"   1. Restricciones del sandbox de Kapso")
                    print(f"   2. Configuración de WhatsApp Business")
                    print(f"   3. Filtros de spam de WhatsApp")

        else:
            print(f"❌ Error enviando mensaje final: {final_response.status_code}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*50)

if __name__ == "__main__":
    check_message_status()