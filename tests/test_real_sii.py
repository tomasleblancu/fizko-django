#!/usr/bin/env python
"""
Prueba del servicio REAL de SII con credenciales de test
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fizko_django.settings')
sys.path.insert(0, '/app')
django.setup()

import logging
from apps.sii.services import create_sii_service, verify_sii_credentials

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_real_sii_authentication():
    """Prueba la autenticación REAL con SII usando Selenium"""
    
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    logger.info("=" * 80)
    logger.info("🌐 PRUEBA DE SERVICIO SII REAL CON SELENIUM")
    logger.info("=" * 80)
    logger.info(f"Tax ID: {tax_id}")
    logger.info(f"Password: {'*' * 12}")
    
    # Test 1: Verificar credenciales con servicio real
    logger.info("\n🔐 Test 1: Verificación de credenciales REALES...")
    try:
        result = verify_sii_credentials(tax_id=tax_id, password=password, use_real=True)
        
        if result['status'] == 'success':
            logger.info("✅ CREDENCIALES REALES VÁLIDAS!")
            data = result.get('data', {})
            logger.info(f"   - RUT: {data.get('tax_id', 'N/A')}")
            logger.info(f"   - Razón Social: {data.get('razon_social', 'N/A')}")
            logger.info(f"   - Estado: {data.get('estado', 'N/A')}")
            logger.info(f"   - Tiempo de ejecución: {result.get('execution_time', 0)}s")
        else:
            logger.error(f"❌ Error en credenciales: {result.get('message')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error al verificar credenciales reales: {e}")
        return False
    
    # Test 2: Obtener datos del contribuyente usando servicio real
    logger.info("\n📊 Test 2: Consulta de contribuyente con servicio REAL...")
    try:
        service = create_sii_service(tax_id=tax_id, password=password, use_real=True)
        
        # Autenticar
        logger.info("🔑 Autenticando...")
        if service.authenticate():
            logger.info("✅ Autenticación exitosa")
            
            # Obtener datos
            logger.info("📋 Obteniendo datos del contribuyente...")
            contribuyente_data = service.consultar_contribuyente()
            
            logger.info("✅ Datos del contribuyente obtenidos:")
            logger.info(f"   - RUT: {contribuyente_data.get('rut', 'N/A')}")
            logger.info(f"   - Razón Social: {contribuyente_data.get('razon_social', 'N/A')}")
            logger.info(f"   - Nombre: {contribuyente_data.get('nombre', 'N/A')}")
            logger.info(f"   - Estado: {contribuyente_data.get('estado', 'N/A')}")
            logger.info(f"   - Dirección: {contribuyente_data.get('direccion', 'N/A')}")
            logger.info(f"   - Comuna: {contribuyente_data.get('comuna', 'N/A')}")
            logger.info(f"   - Email: {contribuyente_data.get('email', 'N/A')}")
            
            # Verificar actividades económicas
            actividades = contribuyente_data.get('actividades_economicas', [])
            if actividades:
                logger.info(f"   - Actividades económicas ({len(actividades)}):")
                for i, act in enumerate(actividades[:3], 1):  # Mostrar máximo 3
                    logger.info(f"     {i}. {act.get('codigo', 'N/A')} - {act.get('descripcion', 'N/A')}")
        else:
            logger.error("❌ Error en autenticación")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error al consultar contribuyente real: {e}")
        return False
    
    # Test 3: Obtener cookies de sesión
    logger.info("\n🍪 Test 3: Obtención de cookies de sesión...")
    try:
        cookies = service.get_cookies()
        logger.info(f"✅ Cookies obtenidas: {len(cookies)} cookies")
        
        # Mostrar las primeras 3 cookies (truncadas por seguridad)
        for i, cookie in enumerate(cookies[:3], 1):
            name = cookie.get('name', 'unknown')
            value = cookie.get('value', '')[:15] + "..."
            domain = cookie.get('domain', 'N/A')
            logger.info(f"   {i}. {name}: {value} (domain: {domain})")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error al obtener cookies: {e}")
        return False

def test_document_simulation():
    """Simula la obtención de documentos tributarios"""
    
    logger.info("\n" + "=" * 80)
    logger.info("📄 SIMULACIÓN DE DOCUMENTOS ELECTRÓNICOS TRIBUTARIOS")
    logger.info("=" * 80)
    
    # Simular documentos de ejemplo basados en datos reales del SII
    documentos_ejemplo = [
        {
            "tipo": "33", "tipo_nombre": "Factura Electrónica",
            "folio": "000001234", "fecha": "2025-08-15",
            "rut_emisor": "76.123.456-7", "razon_social_emisor": "PROVEEDOR ABC LTDA",
            "monto_neto": 2520000, "monto_iva": 478800, "monto_total": 2998800,
            "estado": "ACEPTADO", "trackid": "123456789"
        },
        {
            "tipo": "34", "tipo_nombre": "Factura No Afecta Electrónica", 
            "folio": "000005678", "fecha": "2025-08-20",
            "rut_emisor": "77.987.654-3", "razon_social_emisor": "SERVICIOS XYZ SPA",
            "monto_neto": 1500000, "monto_iva": 0, "monto_total": 1500000,
            "estado": "ACEPTADO", "trackid": "987654321"
        },
        {
            "tipo": "61", "tipo_nombre": "Nota de Crédito Electrónica",
            "folio": "000000123", "fecha": "2025-08-25", 
            "rut_emisor": "76.123.456-7", "razon_social_emisor": "PROVEEDOR ABC LTDA",
            "monto_neto": -252000, "monto_iva": -47880, "monto_total": -299880,
            "estado": "ACEPTADO", "trackid": "456789123"
        }
    ]
    
    logger.info(f"📊 Documentos simulados encontrados: {len(documentos_ejemplo)}")
    logger.info("-" * 80)
    
    total_neto = 0
    total_iva = 0
    total_bruto = 0
    
    for i, doc in enumerate(documentos_ejemplo, 1):
        logger.info(f"\n📄 Documento #{i} - Folio {doc['folio']}")
        logger.info(f"   Tipo: {doc['tipo_nombre']} ({doc['tipo']})")
        logger.info(f"   Fecha: {doc['fecha']}")
        logger.info(f"   Emisor: {doc['razon_social_emisor']}")
        logger.info(f"   RUT Emisor: {doc['rut_emisor']}")
        logger.info(f"   Monto Neto: ${doc['monto_neto']:,}")
        logger.info(f"   IVA: ${doc['monto_iva']:,}")
        logger.info(f"   Total: ${doc['monto_total']:,}")
        logger.info(f"   Estado: {doc['estado']}")
        logger.info(f"   Track ID: {doc['trackid']}")
        
        total_neto += doc['monto_neto']
        total_iva += doc['monto_iva']
        total_bruto += doc['monto_total']
    
    logger.info("\n" + "=" * 80)
    logger.info("📈 RESUMEN FINANCIERO DEL PERÍODO")
    logger.info("=" * 80)
    logger.info(f"Total Neto del Período: ${total_neto:,}")
    logger.info(f"Total IVA del Período: ${total_iva:,}")
    logger.info(f"Total Bruto del Período: ${total_bruto:,}")
    logger.info(f"Número de Documentos: {len(documentos_ejemplo)}")

if __name__ == "__main__":
    logger.info("🚀 INICIANDO PRUEBAS COMPLETAS DE SII")
    
    try:
        # Probar servicio real de SII
        success = test_real_sii_authentication()
        
        if success:
            logger.info("\n🎉 ¡TODAS LAS PRUEBAS REALES EXITOSAS!")
            
            # Mostrar simulación de documentos
            test_document_simulation()
        else:
            logger.warning("\n⚠️ Algunas pruebas fallaron, pero continuando con simulación...")
            test_document_simulation()
            
    except Exception as e:
        logger.error(f"❌ Error general en pruebas: {e}")
    
    logger.info("\n✅ PRUEBAS COMPLETADAS")