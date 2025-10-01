#!/usr/bin/env python
"""
Envía mensaje de prueba al número especificado
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

def send_test_message():
    """Send test message to 56975389973"""
    import requests
    from django.conf import settings
    import logging
    from datetime import datetime

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    target_phone = "56975389973"

    logger.info(f"📱 Sending test message to {target_phone}")

    # Get Kapso configuration
    api_token = getattr(settings, 'KAPSO_API_TOKEN', None)
    base_url = getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')

    if not api_token:
        logger.error("❌ KAPSO_API_TOKEN not configured")
        return False

    headers = {
        'X-API-Key': api_token,
        'Content-Type': 'application/json'
    }

    # Test message with timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    test_message = f"🧪 Mensaje de prueba desde Fizko - {timestamp}\n\n✅ El sistema de verificación está funcionando correctamente!"

    try:
        # Step 1: Find existing conversation for this phone number
        logger.info(f"📞 Looking for conversation with {target_phone}")

        conversations_response = requests.get(
            f'{base_url}/whatsapp_conversations',
            headers=headers,
            timeout=10
        )

        conversation_id = None

        if conversations_response.status_code == 200:
            conversations_data = conversations_response.json()
            conversations = conversations_data.get('data', [])

            # Look for conversation with this phone number
            for conv in conversations:
                conv_phone = conv.get('phone_number', '').replace('+', '')
                if target_phone == conv_phone:
                    conversation_id = conv.get('id')
                    contact_name = conv.get('contact_name', 'Unknown')
                    logger.info(f"✅ Found conversation {conversation_id} for {contact_name} ({target_phone})")
                    break

        if not conversation_id:
            logger.error(f"❌ No conversation found for {target_phone}")
            logger.info("Available conversations:")
            for conv in conversations:
                logger.info(f"  - {conv.get('contact_name', 'Unknown')}: {conv.get('phone_number')}")
            return False

        # Step 2: Send message using the working endpoint
        logger.info(f"📤 Sending test message to conversation {conversation_id}")

        message_payload = {
            'message': {
                'content': test_message,
                'message_type': 'text'
            }
        }

        message_response = requests.post(
            f'{base_url}/whatsapp_conversations/{conversation_id}/whatsapp_messages',
            headers=headers,
            json=message_payload,
            timeout=10
        )

        if message_response.status_code in [200, 201]:
            result = message_response.json()
            message_id = result.get('data', {}).get('id', 'unknown')
            whatsapp_id = result.get('data', {}).get('whatsapp_message_id', 'unknown')

            logger.info(f"✅ SUCCESS! Test message sent to {target_phone}")
            logger.info(f"   Message ID: {message_id}")
            logger.info(f"   WhatsApp ID: {whatsapp_id}")
            logger.info(f"   Status: {result.get('data', {}).get('status', 'unknown')}")

            print(f"🎉 ¡Mensaje enviado exitosamente!")
            print(f"📱 Revisa el WhatsApp +{target_phone} para ver el mensaje")
            print(f"🆔 Message ID: {message_id}")

            return True
        else:
            logger.error(f"❌ Failed to send message: {message_response.status_code}")
            logger.error(f"Response: {message_response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("📱 Enviando mensaje de prueba a +56975389973...")
    print("=" * 50)

    success = send_test_message()

    print("=" * 50)
    if success:
        print("✅ ¡Prueba exitosa!")
    else:
        print("❌ Prueba falló - revisar logs")