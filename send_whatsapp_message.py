#!/usr/bin/env python
"""
Envía mensaje de WhatsApp usando el mismo método que los códigos de verificación
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

def send_whatsapp_message(phone_number, message_text):
    """
    Send WhatsApp message using the same WhatsApp interface used for verification codes

    Args:
        phone_number: Phone number (with country code, e.g., "56975389973")
        message_text: Message to send
    """
    import logging
    from apps.chat.interfaces.whatsapp.whatsapp_interface import WhatsAppInterface
    from datetime import datetime

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Format phone number (add + prefix if not present)
    if not phone_number.startswith('+'):
        phone_number = f'+{phone_number}'

    logger.info(f"📱 Sending WhatsApp message to {phone_number}")

    try:
        # Initialize WhatsApp interface (will use environment config)
        whatsapp_interface = WhatsAppInterface()

        # Send message using the same method as verification codes
        result = whatsapp_interface.send_message(
            recipient=phone_number,
            message=message_text
        )

        if result.get('status') == 'success':
            logger.info(f"✅ SUCCESS! Message sent to {phone_number}")
            logger.info(f"   Message ID: {result.get('message_id', 'unknown')}")
            logger.info(f"   Sent at: {result.get('sent_at', 'unknown')}")

            print(f"\n🎉 ¡Mensaje enviado exitosamente!")
            print(f"📱 Número: {phone_number}")
            print(f"📝 Mensaje: {message_text}")
            print(f"🆔 Message ID: {result.get('message_id', 'unknown')}")

            return True
        else:
            logger.error(f"❌ Failed to send message")
            logger.error(f"Error: {result.get('error', 'Unknown error')}")

            # Check if it's a "graceful" failure (conversation setup needed)
            if result.get('note'):
                logger.info(f"ℹ️ Note: {result.get('note')}")

            return False

    except Exception as e:
        logger.error(f"❌ Error sending message: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    from datetime import datetime

    # Target phone number
    target_phone = "56975389973"

    # Message with timestamp
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"""🚀 ¡Hola desde Fizko!

📅 Fecha y hora: {timestamp}
📱 Sistema: WhatsApp Interface
✅ Mensaje enviado usando el mismo método que los códigos de verificación

¡Este es un mensaje de prueba enviado exitosamente! 🎉"""

    print("📱 Enviando mensaje de WhatsApp...")
    print(f"📞 Destinatario: +{target_phone}")
    print("=" * 50)

    success = send_whatsapp_message(target_phone, message)

    print("=" * 50)
    if success:
        print("✅ ¡Mensaje enviado con éxito!")
    else:
        print("❌ No se pudo enviar el mensaje - revisar logs")