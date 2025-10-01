#!/usr/bin/env python
"""
Diagnóstico completo del sistema de WhatsApp
"""

import os
import sys
import django
from pathlib import Path
import json

# Add the project directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fizko_django.settings')
django.setup()

def diagnose_whatsapp():
    """Diagnóstico completo del sistema de WhatsApp"""
    import requests
    from django.conf import settings
    import logging
    from datetime import datetime

    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    print("\n" + "="*60)
    print("🔍 DIAGNÓSTICO DE SISTEMA WHATSAPP")
    print("="*60)

    # 1. Verificar configuración
    print("\n1️⃣ CONFIGURACIÓN:")
    print("-" * 40)

    api_token = getattr(settings, 'KAPSO_API_TOKEN', None)
    base_url = getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')
    whatsapp_config_id = getattr(settings, 'WHATSAPP_CONFIG_ID', None)

    print(f"✓ API Token: {'✅ Configurado' if api_token else '❌ NO configurado'} ({api_token[:10]}...)" if api_token else "❌ NO configurado")
    print(f"✓ Base URL: {base_url}")
    print(f"✓ WhatsApp Config ID: {whatsapp_config_id}")

    if not api_token:
        print("\n❌ ERROR: No hay token de API configurado")
        return False

    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json'
    }

    # 2. Verificar conexión con API
    print("\n2️⃣ CONEXIÓN CON API KAPSO:")
    print("-" * 40)

    try:
        # Test API health
        test_response = requests.get(
            f'{base_url}/whatsapp_conversations',
            headers=headers,
            timeout=10
        )

        print(f"✓ Estado de API: {test_response.status_code}")

        if test_response.status_code == 200:
            print("✅ API respondiendo correctamente")
        else:
            print(f"❌ API devolvió error: {test_response.status_code}")
            print(f"   Respuesta: {test_response.text[:500]}")
    except Exception as e:
        print(f"❌ Error conectando con API: {e}")
        return False

    # 3. Buscar conversación con el número
    target_phone = "56975389973"
    print(f"\n3️⃣ BUSCANDO CONVERSACIÓN CON +{target_phone}:")
    print("-" * 40)

    try:
        conversations_response = requests.get(
            f'{base_url}/whatsapp_conversations',
            headers=headers,
            timeout=10
        )

        if conversations_response.status_code == 200:
            conversations_data = conversations_response.json()
            conversations = conversations_data.get('data', [])

            print(f"✓ Total de conversaciones: {len(conversations)}")

            # Buscar conversación específica
            found_conversation = None
            for conv in conversations:
                conv_phone = conv.get('phone_number', '').replace('+', '').replace(' ', '')
                if target_phone == conv_phone:
                    found_conversation = conv
                    break

            if found_conversation:
                print(f"✅ Conversación encontrada:")
                print(f"   - ID: {found_conversation.get('id')}")
                print(f"   - Contacto: {found_conversation.get('contact_name', 'Unknown')}")
                print(f"   - Teléfono: {found_conversation.get('phone_number')}")
                print(f"   - Estado: {found_conversation.get('status', 'unknown')}")
                print(f"   - Última actividad: {found_conversation.get('last_message_at', 'N/A')}")

                # 4. Obtener detalles de la conversación
                print(f"\n4️⃣ DETALLES DE LA CONVERSACIÓN:")
                print("-" * 40)

                conv_id = found_conversation.get('id')
                conv_detail_response = requests.get(
                    f'{base_url}/whatsapp_conversations/{conv_id}',
                    headers=headers,
                    timeout=10
                )

                if conv_detail_response.status_code == 200:
                    conv_detail = conv_detail_response.json()
                    data = conv_detail.get('data', {})
                    print(f"   - Mensajes totales: {data.get('message_count', 0)}")
                    print(f"   - WhatsApp Config: {data.get('whatsapp_config_id', 'N/A')}")

                    # Mostrar últimos mensajes
                    messages = data.get('messages', [])
                    if messages:
                        print(f"\n   📨 Últimos {min(3, len(messages))} mensajes:")
                        for msg in messages[:3]:
                            direction = "➡️ Enviado" if msg.get('direction') == 'outbound' else "⬅️ Recibido"
                            status = msg.get('status', 'unknown')
                            content = msg.get('content', '')[:100]
                            created = msg.get('created_at', 'N/A')
                            print(f"      {direction} [{status}]: {content}...")
                            print(f"         Fecha: {created}")

                # 5. Intentar enviar mensaje de prueba
                print(f"\n5️⃣ ENVIANDO MENSAJE DE PRUEBA:")
                print("-" * 40)

                timestamp = datetime.now().strftime("%H:%M:%S")
                test_message = f"🔍 Mensaje de diagnóstico - {timestamp}\n\n✅ Este es un mensaje de prueba para verificar el funcionamiento del sistema."

                message_payload = {
                    'message': {
                        'content': test_message,
                        'message_type': 'text'
                    }
                }

                print(f"   Enviando a conversación ID: {conv_id}")

                send_response = requests.post(
                    f'{base_url}/whatsapp_conversations/{conv_id}/whatsapp_messages',
                    headers=headers,
                    json=message_payload,
                    timeout=30
                )

                if send_response.status_code in [200, 201]:
                    result = send_response.json()
                    data = result.get('data', {})
                    print(f"✅ MENSAJE ENVIADO EXITOSAMENTE")
                    print(f"   - Message ID: {data.get('id', 'N/A')}")
                    print(f"   - WhatsApp ID: {data.get('whatsapp_message_id', 'N/A')}")
                    print(f"   - Estado: {data.get('status', 'N/A')}")
                    print(f"   - Creado: {data.get('created_at', 'N/A')}")

                    # Verificar estado del mensaje enviado
                    if data.get('id'):
                        print(f"\n6️⃣ VERIFICANDO ESTADO DEL MENSAJE:")
                        print("-" * 40)

                        import time
                        time.sleep(2)  # Esperar un poco

                        msg_id = data.get('id')
                        status_response = requests.get(
                            f'{base_url}/whatsapp_messages/{msg_id}',
                            headers=headers,
                            timeout=10
                        )

                        if status_response.status_code == 200:
                            msg_status = status_response.json()
                            msg_data = msg_status.get('data', {})
                            print(f"   - Estado actual: {msg_data.get('status', 'N/A')}")
                            print(f"   - Actualizado: {msg_data.get('updated_at', 'N/A')}")

                            status = msg_data.get('status', '')
                            if status == 'sent':
                                print("   ✅ Mensaje enviado por WhatsApp")
                            elif status == 'delivered':
                                print("   ✅ Mensaje entregado al dispositivo")
                            elif status == 'read':
                                print("   ✅ Mensaje leído por el usuario")
                            elif status == 'failed':
                                print("   ❌ Mensaje falló en el envío")
                                print(f"   Error: {msg_data.get('error_message', 'N/A')}")
                            else:
                                print(f"   ⏳ Estado: {status}")

                else:
                    print(f"❌ Error enviando mensaje: {send_response.status_code}")
                    print(f"   Respuesta: {send_response.text[:500]}")

                    # Intentar decodificar error
                    try:
                        error_data = send_response.json()
                        print(f"   Error detalles: {json.dumps(error_data, indent=2)}")
                    except:
                        pass

            else:
                print(f"❌ No se encontró conversación con +{target_phone}")
                print("\n   Conversaciones disponibles:")
                for conv in conversations[:5]:
                    print(f"   - {conv.get('contact_name', 'Unknown')}: {conv.get('phone_number')}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 7. Verificar configuración de WhatsApp Business
    print(f"\n7️⃣ VERIFICANDO CONFIGURACIÓN WHATSAPP BUSINESS:")
    print("-" * 40)

    if whatsapp_config_id:
        try:
            config_response = requests.get(
                f'{base_url}/whatsapp_configs/{whatsapp_config_id}',
                headers=headers,
                timeout=10
            )

            if config_response.status_code == 200:
                config_data = config_response.json()
                config = config_data.get('data', {})
                print(f"✅ Configuración encontrada:")
                print(f"   - Nombre: {config.get('name', 'N/A')}")
                print(f"   - Número: {config.get('phone_number', 'N/A')}")
                print(f"   - Estado: {config.get('status', 'N/A')}")
            else:
                print(f"❌ No se pudo obtener configuración: {config_response.status_code}")
        except Exception as e:
            print(f"❌ Error verificando configuración: {e}")

    print("\n" + "="*60)
    print("🏁 FIN DEL DIAGNÓSTICO")
    print("="*60)

    return True

if __name__ == "__main__":
    print("🚀 Iniciando diagnóstico de WhatsApp...")
    success = diagnose_whatsapp()

    if success:
        print("\n✅ Diagnóstico completado")
    else:
        print("\n❌ Diagnóstico falló")