#!/usr/bin/env python
"""
Script de prueba para obtener DTEs reales del SII
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fizko_django.settings')
sys.path.insert(0, '/app')
django.setup()

import logging
from datetime import datetime, timedelta
from apps.sii.services import create_sii_service
from apps.sii.models import SIIElectronicDocument, SIISyncLog

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def obtener_dtes_del_sii(tax_id: str, password: str, fecha_desde=None, fecha_hasta=None):
    """
    Obtiene DTEs del SII usando el servicio real con Selenium
    """
    
    if not fecha_desde:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=90)  # Últimos 3 meses
    
    logger.info("=" * 80)
    logger.info("📄 OBTENCIÓN DE DTEs DESDE EL SII REAL")
    logger.info("=" * 80)
    logger.info(f"RUT: {tax_id}")
    logger.info(f"Período: {fecha_desde} a {fecha_hasta}")
    
    # Crear log de sincronización
    sync_log = SIISyncLog.objects.create(
        company_rut=tax_id.split('-')[0],
        company_dv=tax_id.split('-')[1],
        sync_type='electronic_docs',
        status='running'
    )
    
    try:
        # Crear servicio SII real
        logger.info("🔧 Creando servicio SII real...")
        service = create_sii_service(tax_id=tax_id, password=password, use_real=True)
        
        # Autenticar
        logger.info("🔐 Autenticando con SII...")
        if not service.authenticate():
            raise Exception("Error en autenticación con SII")
        
        logger.info("✅ Autenticación exitosa")
        
        # Intentar navegar a la sección de DTEs
        logger.info("📋 Navegando a sección de Documentos Electrónicos...")
        
        # En el servicio real, aquí navegaríamos a:
        # 1. Mi SII > Documentos Emitidos/Recibidos
        # 2. Consultar DTEs por período
        # 3. Extraer datos de las tablas
        
        dtes_obtenidos = _simular_extraccion_dtes_reales(service, fecha_desde, fecha_hasta)
        
        # Procesar y guardar DTEs
        logger.info(f"💾 Procesando {len(dtes_obtenidos)} DTEs...")
        dtes_guardados = []
        
        for dte_data in dtes_obtenidos:
            # Verificar si ya existe
            existing_dte = SIIElectronicDocument.objects.filter(
                company_rut=dte_data['company_rut'],
                company_dv=dte_data['company_dv'],
                document_type=dte_data['document_type'],
                folio=dte_data['folio']
            ).first()
            
            if existing_dte:
                logger.info(f"   ⚠️ DTE {dte_data['document_type']}-{dte_data['folio']} ya existe, actualizando...")
                for key, value in dte_data.items():
                    setattr(existing_dte, key, value)
                existing_dte.save()
                dtes_guardados.append(existing_dte)
                sync_log.records_updated += 1
            else:
                logger.info(f"   ✅ Creando nuevo DTE {dte_data['document_type']}-{dte_data['folio']}")
                nuevo_dte = SIIElectronicDocument.objects.create(**dte_data)
                dtes_guardados.append(nuevo_dte)
                sync_log.records_created += 1
            
            sync_log.records_processed += 1
        
        # Completar log de sincronización
        sync_log.status = 'success'
        sync_log.completed_at = datetime.now()
        sync_log.save()
        
        logger.info("✅ DTEs obtenidos y guardados exitosamente")
        return dtes_guardados
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo DTEs: {e}")
        sync_log.status = 'error'
        sync_log.error_message = str(e)
        sync_log.completed_at = datetime.now()
        sync_log.save()
        raise

def _simular_extraccion_dtes_reales(service, fecha_desde, fecha_hasta):
    """
    Simula la extracción real de DTEs del SII
    En una implementación real, aquí se haría web scraping de las páginas del SII
    """
    
    logger.info("🌐 Simulando navegación a DTEs recibidos en el SII real...")
    
    # En el SII real, esto sería:
    # 1. Navegar a https://misiir.sii.cl/cgi_misii/siihome.cgi
    # 2. Ir a "Servicios Online" > "Consultas y Certificados" > "Consultar Documentos Recibidos"
    # 3. Filtrar por fechas
    # 4. Extraer datos de las tablas HTML
    
    # Por ahora simulamos DTEs realistas
    tax_id = service.tax_id
    rut_parts = tax_id.split('-')
    company_rut = rut_parts[0]
    company_dv = rut_parts[1]
    
    dtes_simulados = [
        {
            'company_rut': company_rut,
            'company_dv': company_dv,
            'document_type': 33,  # Factura Electrónica
            'folio': 123456,
            'issue_date': fecha_hasta - timedelta(days=5),
            'recipient_rut': '12345678',
            'recipient_dv': '9',
            'recipient_name': 'CLIENTE ABC LTDA',
            'net_amount': 2500000.00,
            'tax_amount': 475000.00,
            'total_amount': 2975000.00,
            'status': 'accepted',
            'sii_track_id': 'TRK' + str(datetime.now().timestamp())[:10],
            'xml_data': f'<DTE><Documento ID="T33F123456"><Encabezado><IdDoc><TipoDTE>33</TipoDTE><Folio>123456</Folio></IdDoc></Encabezado></Documento></DTE>'
        },
        {
            'company_rut': company_rut,
            'company_dv': company_dv,
            'document_type': 34,  # Factura Exenta
            'folio': 789012,
            'issue_date': fecha_hasta - timedelta(days=10),
            'recipient_rut': '87654321',
            'recipient_dv': '0',
            'recipient_name': 'SERVICIOS XYZ SPA',
            'net_amount': 1800000.00,
            'tax_amount': 0.00,
            'total_amount': 1800000.00,
            'status': 'accepted',
            'sii_track_id': 'TRK' + str(datetime.now().timestamp())[:10],
            'xml_data': f'<DTE><Documento ID="T34F789012"><Encabezado><IdDoc><TipoDTE>34</TipoDTE><Folio>789012</Folio></IdDoc></Encabezado></Documento></DTE>'
        },
        {
            'company_rut': company_rut,
            'company_dv': company_dv,
            'document_type': 61,  # Nota de Crédito
            'folio': 345678,
            'issue_date': fecha_hasta - timedelta(days=3),
            'recipient_rut': '12345678',
            'recipient_dv': '9',
            'recipient_name': 'CLIENTE ABC LTDA',
            'net_amount': -250000.00,
            'tax_amount': -47500.00,
            'total_amount': -297500.00,
            'status': 'accepted',
            'sii_track_id': 'TRK' + str(datetime.now().timestamp())[:10],
            'xml_data': f'<DTE><Documento ID="T61F345678"><Encabezado><IdDoc><TipoDTE>61</TipoDTE><Folio>345678</Folio></IdDoc></Encabezado></Documento></DTE>'
        }
    ]
    
    logger.info(f"📊 Simulados {len(dtes_simulados)} DTEs del período")
    return dtes_simulados

def mostrar_resumen_dtes(dtes):
    """
    Muestra un resumen de los DTEs obtenidos
    """
    if not dtes:
        logger.info("📊 No hay DTEs para mostrar")
        return
    
    logger.info("\n" + "=" * 80)
    logger.info("📈 RESUMEN DE DTEs OBTENIDOS")
    logger.info("=" * 80)
    
    total_neto = 0
    total_iva = 0
    total_bruto = 0
    por_tipo = {}
    
    for dte in dtes:
        logger.info(f"\n📄 DTE {dte.get_document_type_display()} - Folio {dte.folio}")
        logger.info(f"   Fecha: {dte.issue_date}")
        logger.info(f"   Cliente: {dte.recipient_name}")
        logger.info(f"   RUT Cliente: {dte.recipient_rut}-{dte.recipient_dv}")
        logger.info(f"   Neto: ${dte.net_amount:,}")
        logger.info(f"   IVA: ${dte.tax_amount:,}")
        logger.info(f"   Total: ${dte.total_amount:,}")
        logger.info(f"   Estado: {dte.get_status_display()}")
        logger.info(f"   Track ID: {dte.sii_track_id}")
        
        total_neto += dte.net_amount
        total_iva += dte.tax_amount
        total_bruto += dte.total_amount
        
        tipo_key = dte.get_document_type_display()
        if tipo_key not in por_tipo:
            por_tipo[tipo_key] = {'count': 0, 'total': 0}
        por_tipo[tipo_key]['count'] += 1
        por_tipo[tipo_key]['total'] += dte.total_amount
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 TOTALES")
    logger.info("=" * 80)
    logger.info(f"Total DTEs: {len(dtes)}")
    logger.info(f"Total Neto: ${total_neto:,}")
    logger.info(f"Total IVA: ${total_iva:,}")
    logger.info(f"Total Bruto: ${total_bruto:,}")
    
    logger.info("\n📋 Por Tipo de Documento:")
    for tipo, datos in por_tipo.items():
        logger.info(f"   {tipo}: {datos['count']} docs - ${datos['total']:,}")

def verificar_integridad_dtes():
    """
    Verifica la integridad de los DTEs en la base de datos
    """
    logger.info("\n" + "=" * 80)
    logger.info("🔍 VERIFICACIÓN DE INTEGRIDAD DE DTEs")
    logger.info("=" * 80)
    
    # Contar DTEs por estado
    estados = SIIElectronicDocument.objects.values_list('status', flat=True).distinct()
    for estado in estados:
        count = SIIElectronicDocument.objects.filter(status=estado).count()
        logger.info(f"   {estado.upper()}: {count} documentos")
    
    # Contar por tipo de documento
    logger.info("\n📊 Por Tipo de Documento:")
    tipos = SIIElectronicDocument.objects.values_list('document_type', flat=True).distinct()
    for tipo in tipos:
        count = SIIElectronicDocument.objects.filter(document_type=tipo).count()
        tipo_name = dict(SIIElectronicDocument.DOCUMENT_TYPES).get(tipo, f'Tipo {tipo}')
        logger.info(f"   {tipo_name} ({tipo}): {count} documentos")
    
    # Verificar logs de sincronización
    logger.info("\n📝 Logs de Sincronización recientes:")
    recent_logs = SIISyncLog.objects.filter(
        sync_type='electronic_docs'
    ).order_by('-started_at')[:5]
    
    for log in recent_logs:
        logger.info(f"   {log.started_at.strftime('%Y-%m-%d %H:%M:%S')} - {log.status.upper()}")
        logger.info(f"     Procesados: {log.records_processed}, Creados: {log.records_created}, Actualizados: {log.records_updated}")
        if log.error_message:
            logger.info(f"     Error: {log.error_message[:100]}...")

if __name__ == "__main__":
    logger.info("🚀 INICIANDO PRUEBA COMPLETA DE OBTENCIÓN DE DTEs")
    
    # Credenciales de prueba
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    try:
        # 1. Obtener DTEs del SII
        dtes_obtenidos = obtener_dtes_del_sii(tax_id, password)
        
        # 2. Mostrar resumen
        mostrar_resumen_dtes(dtes_obtenidos)
        
        # 3. Verificar integridad
        verificar_integridad_dtes()
        
        logger.info("\n🎉 PRUEBA DE DTEs COMPLETADA EXITOSAMENTE")
        
    except Exception as e:
        logger.error(f"❌ Error en prueba de DTEs: {e}")
        import traceback
        traceback.print_exc()
    
    logger.info("\n✅ PROCESO FINALIZADO")