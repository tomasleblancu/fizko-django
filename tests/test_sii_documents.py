#!/usr/bin/env python
"""
Script de prueba para obtener documentos electrónicos tributarios del SII
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fizko_django.settings.development')
sys.path.insert(0, '/app')
django.setup()

import logging
from datetime import datetime, timedelta
from apps.sii.services import create_sii_service, verify_sii_credentials
from apps.sii.sii_rpa_service import RealSIIService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_sii_authentication():
    """Prueba la autenticación con SII"""
    
    # Obtener credenciales del entorno
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    logger.info("=" * 60)
    logger.info("🔐 PRUEBA DE AUTENTICACIÓN SII")
    logger.info("=" * 60)
    logger.info(f"Tax ID: {tax_id}")
    logger.info(f"Password: {'*' * 8}")
    
    # Probar verificación de credenciales
    logger.info("\n📊 Verificando credenciales...")
    result = verify_sii_credentials(tax_id=tax_id, password=password, use_real=False)
    
    if result['status'] == 'success':
        logger.info("✅ Credenciales válidas")
        logger.info(f"   - Razón Social: {result['data'].get('razon_social', 'N/A')}")
        logger.info(f"   - Estado: {result['data'].get('estado', 'N/A')}")
        logger.info(f"   - Dirección: {result['data'].get('direccion', 'N/A')}")
        return True
    else:
        logger.error(f"❌ Error al verificar credenciales: {result.get('message')}")
        return False

def test_get_electronic_documents():
    """Prueba obtener documentos electrónicos del SII"""
    
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    logger.info("\n" + "=" * 60)
    logger.info("📄 PRUEBA DE OBTENCIÓN DE DOCUMENTOS ELECTRÓNICOS")
    logger.info("=" * 60)
    
    # Crear servicio SII
    logger.info("\n🔧 Creando servicio SII...")
    service = create_sii_service(tax_id=tax_id, password=password, use_real=False)
    
    # Autenticar
    logger.info("🔐 Autenticando...")
    if service.authenticate():
        logger.info("✅ Autenticación exitosa")
    else:
        logger.error("❌ Error en autenticación")
        return
    
    # Como estamos usando el servicio mock, simularemos documentos de ejemplo
    logger.info("\n📋 Simulando obtención de documentos (servicio mock)...")
    
    # Fechas de búsqueda (último mes)
    fecha_hasta = datetime.now()
    fecha_desde = fecha_hasta - timedelta(days=30)
    
    logger.info(f"   Período: {fecha_desde.strftime('%Y-%m-%d')} a {fecha_hasta.strftime('%Y-%m-%d')}")
    
    # Documentos mock de ejemplo
    documentos_mock = [
        {
            "tipo": "33",
            "tipo_nombre": "Factura Electrónica",
            "folio": "12345",
            "fecha": "2025-08-15",
            "rut_emisor": "76123456-7",
            "razon_social_emisor": "PROVEEDOR TEST S.A.",
            "monto_total": 1500000,
            "monto_neto": 1260504,
            "monto_iva": 239496,
            "estado": "ACEPTADO"
        },
        {
            "tipo": "34",
            "tipo_nombre": "Factura No Afecta o Exenta Electrónica",
            "folio": "67890",
            "fecha": "2025-08-20",
            "rut_emisor": "77987654-3",
            "razon_social_emisor": "SERVICIOS PROFESIONALES LTDA",
            "monto_total": 800000,
            "monto_neto": 800000,
            "monto_iva": 0,
            "estado": "ACEPTADO"
        },
        {
            "tipo": "61",
            "tipo_nombre": "Nota de Crédito Electrónica",
            "folio": "5432",
            "fecha": "2025-08-25",
            "rut_emisor": "76123456-7",
            "razon_social_emisor": "PROVEEDOR TEST S.A.",
            "monto_total": -150000,
            "monto_neto": -126050,
            "monto_iva": -23950,
            "estado": "ACEPTADO"
        }
    ]
    
    logger.info(f"\n📊 Documentos encontrados: {len(documentos_mock)}")
    logger.info("-" * 60)
    
    total_compras = 0
    total_ventas = 0
    
    for doc in documentos_mock:
        logger.info(f"\n📄 Documento #{doc['folio']}")
        logger.info(f"   Tipo: {doc['tipo_nombre']} ({doc['tipo']})")
        logger.info(f"   Fecha: {doc['fecha']}")
        logger.info(f"   Emisor: {doc['razon_social_emisor']} ({doc['rut_emisor']})")
        logger.info(f"   Monto Neto: ${doc['monto_neto']:,}")
        logger.info(f"   IVA: ${doc['monto_iva']:,}")
        logger.info(f"   Monto Total: ${doc['monto_total']:,}")
        logger.info(f"   Estado: {doc['estado']}")
        
        if doc['monto_total'] > 0:
            total_compras += doc['monto_total']
        else:
            total_ventas += abs(doc['monto_total'])
    
    logger.info("\n" + "=" * 60)
    logger.info("📈 RESUMEN")
    logger.info("=" * 60)
    logger.info(f"Total Compras: ${total_compras:,}")
    logger.info(f"Total Notas de Crédito: ${total_ventas:,}")
    logger.info(f"Neto del Período: ${total_compras - total_ventas:,}")

def test_real_sii_service():
    """Prueba el servicio real de SII con Selenium (si está disponible)"""
    
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    logger.info("\n" + "=" * 60)
    logger.info("🌐 PRUEBA DE SERVICIO SII REAL (SELENIUM)")
    logger.info("=" * 60)
    
    try:
        from apps.sii.sii_rpa_service import RealSIIService
        
        logger.info("🚀 Iniciando servicio real con Selenium...")
        service = RealSIIService(tax_id=tax_id, password=password, headless=True)
        
        logger.info("🔐 Intentando autenticación real...")
        if service.authenticate():
            logger.info("✅ Autenticación real exitosa!")
            logger.info("🍪 Cookies obtenidas:")
            cookies = service.get_cookies()
            for cookie in cookies[:3]:  # Mostrar solo las primeras 3 cookies
                logger.info(f"   - {cookie.get('name', 'unknown')}: {cookie.get('value', '')[:20]}...")
        else:
            logger.warning("⚠️ No se pudo autenticar con el servicio real")
            
    except ImportError as e:
        logger.warning(f"⚠️ Selenium no disponible: {e}")
        logger.info("📝 Usando servicio mock como fallback")
    except Exception as e:
        logger.error(f"❌ Error al usar servicio real: {e}")
        logger.info("📝 Usando servicio mock como fallback")

if __name__ == "__main__":
    logger.info("\n🚀 INICIANDO PRUEBAS DE DOCUMENTOS ELECTRÓNICOS SII\n")
    
    # 1. Probar autenticación
    if test_sii_authentication():
        # 2. Probar obtención de documentos
        test_get_electronic_documents()
        
        # 3. Probar servicio real (opcional)
        test_real_sii_service()
    
    logger.info("\n✅ PRUEBAS COMPLETADAS\n")