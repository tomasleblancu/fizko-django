from django.db import transaction
from .models import MessageTemplate


def create_default_templates(company):
    """
    Crea plantillas por defecto para una empresa
    """
    default_templates = [
        {
            'name': 'recordatorio_f29',
            'template_type': 'tax_reminder',
            'subject': 'Recordatorio F29',
            'body_text': '''Hola {contact_name},

Te recordamos que el Formulario 29 de {period_month}/{period_year} vence el {due_date}.

📋 **Detalles:**
• Empresa: {company_name}
• RUT: {company_rut}
• Período: {period_month}/{period_year}
• Fecha límite: {due_date}

Si necesitas ayuda o tienes consultas, no dudes en contactarnos.

Saludos,
Equipo Fizko''',
            'footer_text': 'Fizko - Tu asistente tributario',
            'available_variables': [
                'contact_name', 'company_name', 'company_rut', 
                'period_month', 'period_year', 'due_date'
            ]
        },
        {
            'name': 'recordatorio_f3323',
            'template_type': 'tax_reminder',
            'subject': 'Recordatorio F3323',
            'body_text': '''Hola {contact_name},

El Formulario 3323 de {period_month}/{period_year} debe ser presentado antes del {due_date}.

📊 **Información importante:**
• Empresa: {company_name}
• RUT: {company_rut}
• Período: {period_month}/{period_year}
• Vencimiento: {due_date}

¡No olvides cumplir con tus obligaciones tributarias!

Equipo Fizko''',
            'footer_text': 'Fizko - Contabilidad simplificada',
            'available_variables': [
                'contact_name', 'company_name', 'company_rut', 
                'period_month', 'period_year', 'due_date'
            ]
        },
        {
            'name': 'nuevo_dte_recibido',
            'template_type': 'document_alert',
            'subject': 'Nuevo DTE Recibido',
            'body_text': '''Nuevo documento recibido en {company_name}:

📄 **{document_type}** #{document_number}
💰 Monto: ${amount}
📅 Fecha: {document_date}
🏢 Emisor: {issuer_name}

El documento ha sido registrado automáticamente en tu sistema.

Puedes revisarlo en: {document_url}''',
            'footer_text': 'Automatizado por Fizko',
            'available_variables': [
                'company_name', 'document_type', 'document_number',
                'amount', 'document_date', 'issuer_name', 'document_url'
            ]
        },
        {
            'name': 'pago_vencido',
            'template_type': 'payment_due',
            'subject': 'Pago Vencido',
            'body_text': '''⚠️ **PAGO VENCIDO**

{contact_name}, tienes un pago pendiente:

💸 **{payment_description}**
• Monto: ${amount}
• Fecha vencimiento: {due_date}
• Días vencido: {days_overdue}

Por favor, regulariza tu situación a la brevedad para evitar multas e intereses.

¿Necesitas ayuda? Contáctanos.''',
            'footer_text': 'Fizko - Control tributario',
            'available_variables': [
                'contact_name', 'payment_description', 'amount',
                'due_date', 'days_overdue'
            ]
        },
        {
            'name': 'bienvenida',
            'template_type': 'welcome',
            'subject': 'Bienvenido a Fizko',
            'body_text': '''¡Bienvenido a Fizko! 🎉

Hola {contact_name}, ahora puedes recibir notificaciones importantes sobre {company_name} directamente por WhatsApp.

📱 **Recibirás alertas sobre:**
• Vencimientos de formularios (F29, F3323)
• Nuevos documentos tributarios
• Recordatorios de pagos
• Actualizaciones del sistema

Si tienes dudas, escribe "ayuda" en cualquier momento.

¡Estamos aquí para simplificar tu contabilidad!''',
            'footer_text': 'Fizko - Tu socio contable',
            'available_variables': ['contact_name', 'company_name']
        },
        {
            'name': 'soporte_ayuda',
            'template_type': 'support',
            'subject': 'Menú de Ayuda',
            'body_text': '''¿En qué te podemos ayudar?

📋 **Opciones disponibles:**

1️⃣ **Estado de formularios**: Consulta F29, F3323 pendientes
2️⃣ **Documentos recientes**: Ver últimas facturas/boletas
3️⃣ **Próximos vencimientos**: Fechas importantes
4️⃣ **Soporte técnico**: Contacto con nuestro equipo
5️⃣ **Configuración**: Ajustar notificaciones

Responde con el número de la opción o describe tu consulta.''',
            'footer_text': 'Estamos aquí para ayudarte',
            'available_variables': []
        },
        {
            'name': 'error_sincronizacion',
            'template_type': 'support',
            'subject': 'Error de Sincronización',
            'body_text': '''❌ **Error de Sincronización**

{contact_name}, hemos detectado un problema al sincronizar los datos de {company_name} con el SII.

🔍 **Detalles del error:**
• Tipo: {error_type}
• Hora: {error_time}
• Descripción: {error_message}

**¿Qué hacer ahora?**
1. Verifica tus credenciales del SII
2. Revisa tu conexión a internet
3. Si persiste, contacta a soporte

Nos encargaremos de resolver esto pronto.''',
            'footer_text': 'Soporte Fizko 24/7',
            'available_variables': [
                'contact_name', 'company_name', 'error_type',
                'error_time', 'error_message'
            ]
        },
        {
            'name': 'confirmacion_pago',
            'template_type': 'custom',
            'subject': 'Confirmación de Pago',
            'body_text': '''✅ **Pago Confirmado**

{contact_name}, hemos registrado tu pago:

💳 **{payment_type}**
• Monto: ${amount}
• Fecha: {payment_date}
• Referencia: {reference_number}

Tu comprobante está disponible en el sistema.

¡Gracias por mantenerte al día con tus obligaciones!''',
            'footer_text': 'Fizko - Pagos y contabilidad',
            'available_variables': [
                'contact_name', 'payment_type', 'amount',
                'payment_date', 'reference_number'
            ]
        }
    ]
    
    created_templates = []
    
    with transaction.atomic():
        for template_data in default_templates:
            template, created = MessageTemplate.objects.get_or_create(
                company=company,
                name=template_data['name'],
                defaults=template_data
            )
            
            if created:
                created_templates.append(template)
                print(f"✅ Plantilla creada: {template.name}")
            else:
                print(f"ℹ️ Plantilla ya existe: {template.name}")
    
    return created_templates


def create_chile_specific_templates(company):
    """
    Crea plantillas específicas para el sistema tributario chileno
    """
    chile_templates = [
        {
            'name': 'recordatorio_operacion_renta',
            'template_type': 'tax_reminder',
            'subject': 'Operación Renta',
            'body_text': '''📊 **Operación Renta {tax_year}**

{contact_name}, se acerca la Operación Renta:

📅 **Fechas importantes:**
• Inicio: {start_date}
• Empresas: {company_deadline}
• Personas: {person_deadline}

📋 **Para {company_name} necesitarás:**
• Balance tributario
• Inventario final
• Libro de compras y ventas
• Formularios auxiliares

¿Necesitas ayuda con la preparación? Contáctanos.''',
            'footer_text': 'Fizko - Especialistas en tributación chilena',
            'available_variables': [
                'contact_name', 'company_name', 'tax_year',
                'start_date', 'company_deadline', 'person_deadline'
            ]
        },
        {
            'name': 'recordatorio_primera_categoria',
            'template_type': 'tax_reminder',
            'subject': 'Impuesto Primera Categoría',
            'body_text': '''🏢 **Impuesto Primera Categoría**

{contact_name}, recordatorio para {company_name}:

📊 **Período:** {period_year}
💰 **Impuesto estimado:** ${estimated_tax}
📅 **Vencimiento:** {due_date}

**Documentos requeridos:**
• Formulario 22
• Balance tributario
• Estado de resultados

¡Prepara tu declaración con tiempo!''',
            'footer_text': 'Fizko - Tu asesor tributario',
            'available_variables': [
                'contact_name', 'company_name', 'period_year',
                'estimated_tax', 'due_date'
            ]
        },
        {
            'name': 'alerta_dte_rechazado',
            'template_type': 'document_alert',
            'subject': 'DTE Rechazado',
            'body_text': '''❌ **Documento Tributario Rechazado**

{contact_name}, el DTE ha sido rechazado por el SII:

📄 **{document_type}** #{document_number}
⚠️ **Motivo:** {rejection_reason}
📅 **Fecha rechazo:** {rejection_date}

**Acción requerida:**
1. Corrige los errores indicados
2. Reenvía el documento
3. Notifica al receptor si aplica

Tiempo límite para corrección: {correction_deadline}''',
            'footer_text': 'Fizko - Gestión de DTEs',
            'available_variables': [
                'contact_name', 'document_type', 'document_number',
                'rejection_reason', 'rejection_date', 'correction_deadline'
            ]
        },
        {
            'name': 'resumen_mensual',
            'template_type': 'custom',
            'subject': 'Resumen Mensual',
            'body_text': '''📈 **Resumen de {month_name} {year}**

{contact_name}, aquí tienes el resumen de {company_name}:

💰 **Financiero:**
• Ventas: ${total_sales}
• Compras: ${total_purchases}
• IVA por pagar: ${iva_payable}

📄 **Documentos:**
• Facturas emitidas: {invoices_issued}
• Boletas emitidas: {receipts_issued}
• Documentos recibidos: {documents_received}

✅ **Cumplimiento:**
• F29 presentado: {f29_status}
• DTEs al día: {dte_compliance}%

¿Necesitas el reporte completo? Solicítalo aquí.''',
            'footer_text': 'Fizko - Control total de tu negocio',
            'available_variables': [
                'contact_name', 'company_name', 'month_name', 'year',
                'total_sales', 'total_purchases', 'iva_payable',
                'invoices_issued', 'receipts_issued', 'documents_received',
                'f29_status', 'dte_compliance'
            ]
        }
    ]
    
    created_templates = []
    
    with transaction.atomic():
        for template_data in chile_templates:
            template, created = MessageTemplate.objects.get_or_create(
                company=company,
                name=template_data['name'],
                defaults=template_data
            )
            
            if created:
                created_templates.append(template)
                print(f"✅ Plantilla chilena creada: {template.name}")
    
    return created_templates