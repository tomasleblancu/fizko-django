#!/usr/bin/env python
"""
Prueba de extracción REAL de DTEs desde el SII
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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_real_dte_extraction():
    """
    Prueba la extracción REAL de DTEs desde el SII
    """
    
    # Credenciales de prueba
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    logger.info("=" * 80)
    logger.info("🌐 PRUEBA DE EXTRACCIÓN REAL DE DTEs DESDE EL SII")
    logger.info("=" * 80)
    logger.info(f"RUT: {tax_id}")
    
    # Definir período de búsqueda (últimas 2 semanas)
    fecha_hasta = datetime.now().date()
    fecha_desde = fecha_hasta - timedelta(days=14)
    
    logger.info(f"Período de búsqueda: {fecha_desde} a {fecha_hasta}")
    
    try:
        # 1. Crear servicio SII real
        logger.info("\n🔧 1. Creando servicio SII real...")
        service = create_sii_service(tax_id=tax_id, password=password, use_real=True)
        
        # 2. Autenticar
        logger.info("\n🔐 2. Autenticando con SII...")
        if not service.authenticate():
            raise Exception("Error en autenticación")
        
        logger.info("✅ Autenticación exitosa")
        
        # 3. Intentar extraer DTEs recibidos
        logger.info("\n📄 3. Extrayendo DTEs RECIBIDOS...")
        dtes_recibidos = service.obtener_dtes_reales(
            fecha_desde=fecha_desde.strftime('%Y-%m-%d'),
            fecha_hasta=fecha_hasta.strftime('%Y-%m-%d'),
            tipo_operacion='recibidos'
        )
        
        logger.info(f"✅ DTEs recibidos extraídos: {len(dtes_recibidos)}")
        
        if dtes_recibidos:
            logger.info("\n📋 DTEs RECIBIDOS encontrados:")
            for i, dte in enumerate(dtes_recibidos[:5], 1):
                logger.info(f"   {i}. Folio: {dte.get('folio', 'N/A')}")
                logger.info(f"      Emisor: {dte.get('rut_emisor', 'N/A')}")
                logger.info(f"      Razón Social: {dte.get('razon_social_emisor', 'N/A')}")
                logger.info(f"      Fecha: {dte.get('fecha_emision', 'N/A')}")
                logger.info(f"      Monto: {dte.get('monto_total', 'N/A')}")
                logger.info(f"      Fuente: {dte.get('_source', 'N/A')}")
        else:
            logger.info("ℹ️ No se encontraron DTEs recibidos en el período")
        
        # 4. Intentar extraer DTEs emitidos (opcional)
        logger.info("\n📤 4. Extrayendo DTEs EMITIDOS...")
        try:
            dtes_emitidos = service.obtener_dtes_reales(
                fecha_desde=fecha_desde.strftime('%Y-%m-%d'),
                fecha_hasta=fecha_hasta.strftime('%Y-%m-%d'),
                tipo_operacion='emitidos'
            )
            
            logger.info(f"✅ DTEs emitidos extraídos: {len(dtes_emitidos)}")
            
            if dtes_emitidos:
                logger.info("\n📋 DTEs EMITIDOS encontrados:")
                for i, dte in enumerate(dtes_emitidos[:3], 1):
                    logger.info(f"   {i}. Folio: {dte.get('folio', 'N/A')}")
                    logger.info(f"      Receptor: {dte.get('rut_emisor', 'N/A')}")
                    logger.info(f"      Monto: {dte.get('monto_total', 'N/A')}")
            else:
                logger.info("ℹ️ No se encontraron DTEs emitidos en el período")
                
        except Exception as e:
            logger.warning(f"⚠️ Error extrayendo DTEs emitidos: {e}")
        
        # 5. Resumen final
        total_dtes = len(dtes_recibidos) + len(dtes_emitidos if 'dtes_emitidos' in locals() else [])
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMEN DE EXTRACCIÓN REAL")
        logger.info("=" * 80)
        logger.info(f"DTEs Recibidos: {len(dtes_recibidos)}")
        logger.info(f"DTEs Emitidos: {len(dtes_emitidos if 'dtes_emitidos' in locals() else [])}")
        logger.info(f"Total DTEs: {total_dtes}")
        logger.info(f"Período consultado: {fecha_desde} a {fecha_hasta}")
        
        if total_dtes > 0:
            logger.info("🎉 ¡EXTRACCIÓN REAL DE DTEs EXITOSA!")
        else:
            logger.info("ℹ️ No se encontraron DTEs en el período, pero la extracción funcionó")
        
        # 6. Cerrar servicio
        service.close()
        logger.info("🔴 Servicio SII cerrado")
        
        return dtes_recibidos, dtes_emitidos if 'dtes_emitidos' in locals() else []
        
    except Exception as e:
        logger.error(f"❌ Error en extracción real de DTEs: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def test_different_date_ranges():
    """
    Prueba con diferentes rangos de fechas
    """
    
    logger.info("\n" + "=" * 80)  
    logger.info("📅 PRUEBA CON DIFERENTES RANGOS DE FECHAS")
    logger.info("=" * 80)
    
    tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
    password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
    
    # Diferentes períodos para probar
    periodos = [
        # Último mes completo
        {
            'nombre': 'Último mes',
            'desde': (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1),
            'hasta': datetime.now().replace(day=1) - timedelta(days=1)
        },
        # Últimos 7 días
        {
            'nombre': 'Últimos 7 días',
            'desde': datetime.now() - timedelta(days=7),
            'hasta': datetime.now()
        },
        # Agosto 2025
        {
            'nombre': 'Agosto 2025',
            'desde': datetime(2025, 8, 1),
            'hasta': datetime(2025, 8, 31)
        }
    ]
    
    resultados = {}
    
    try:
        service = create_sii_service(tax_id=tax_id, password=password, use_real=True)
        
        if not service.authenticate():
            logger.error("❌ No se pudo autenticar")
            return
        
        for periodo in periodos:
            logger.info(f"\n📆 Probando período: {periodo['nombre']}")
            logger.info(f"   Desde: {periodo['desde'].date()}")
            logger.info(f"   Hasta: {periodo['hasta'].date()}")
            
            try:
                dtes = service.obtener_dtes_reales(
                    fecha_desde=periodo['desde'].strftime('%Y-%m-%d'),
                    fecha_hasta=periodo['hasta'].strftime('%Y-%m-%d'),
                    tipo_operacion='recibidos'
                )
                
                resultados[periodo['nombre']] = len(dtes)
                logger.info(f"   ✅ DTEs encontrados: {len(dtes)}")
                
                # Si encontramos DTEs, mostrar algunos detalles
                if dtes:
                    logger.info("   📋 Primeros DTEs:")
                    for dte in dtes[:2]:
                        logger.info(f"     - Folio: {dte.get('folio')}, Monto: {dte.get('monto_total')}")
                
            except Exception as e:
                logger.error(f"   ❌ Error en período {periodo['nombre']}: {e}")
                resultados[periodo['nombre']] = 0
        
        service.close()
        
    except Exception as e:
        logger.error(f"❌ Error general en prueba de períodos: {e}")
    
    # Resumen de resultados por período
    logger.info("\n📊 RESUMEN POR PERÍODOS:")
    for periodo, cantidad in resultados.items():
        logger.info(f"   {periodo}: {cantidad} DTEs")

if __name__ == "__main__":
    logger.info("🚀 INICIANDO PRUEBAS DE EXTRACCIÓN REAL DE DTEs")
    
    try:
        # Prueba principal
        dtes_recibidos, dtes_emitidos = test_real_dte_extraction()
        
        # Si la prueba principal funcionó, probar diferentes períodos
        if len(dtes_recibidos) > 0 or len(dtes_emitidos) > 0:
            logger.info("\n🔄 Dado que la extracción básica funcionó, probando más períodos...")
            test_different_date_ranges()
        
    except Exception as e:
        logger.error(f"❌ Error general: {e}")
    
    logger.info("\n✅ PRUEBAS COMPLETADAS")