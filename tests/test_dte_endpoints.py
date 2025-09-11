#!/usr/bin/env python
"""
Test de endpoints de DTEs obtenidos del SII
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_list_dtes():
    """Test endpoint para listar DTEs"""
    print("📋 Probando endpoint de listado de DTEs...")
    
    try:
        # Sin filtros
        response = requests.get(f"{BASE_URL}/sii/dtes/", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ DTEs encontrados: {data.get('total_count', 0)}")
            print(f"   Resultados en página: {data.get('count', 0)}")
            
            # Mostrar primeros DTEs
            for i, dte in enumerate(data.get('results', [])[:3], 1):
                print(f"   {i}. {dte['document_type_name']} #{dte['folio']} - ${dte['total_amount']:,}")
                print(f"      Cliente: {dte['recipient_name']} ({dte['recipient_rut']})")
                print(f"      Fecha: {dte['issue_date']} - Estado: {dte['status_display']}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_list_dtes_with_filters():
    """Test endpoint con filtros"""
    print("\n🔍 Probando endpoint con filtros...")
    
    try:
        params = {
            'company_rut': '77794858',
            'fecha_desde': '2025-08-01',
            'fecha_hasta': '2025-08-31',
            'limit': 10
        }
        
        response = requests.get(f"{BASE_URL}/sii/dtes/", params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ DTEs filtrados: {data.get('total_count', 0)}")
            for dte in data.get('results', []):
                print(f"   - {dte['document_type_name']} #{dte['folio']} - ${dte['total_amount']:,}")
        else:
            print(f"❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_dte_detail():
    """Test endpoint de detalle de DTE"""
    print("\n📄 Probando endpoint de detalle de DTE...")
    
    try:
        # Primero obtener ID de un DTE
        list_response = requests.get(f"{BASE_URL}/sii/dtes/", timeout=30)
        if list_response.status_code == 200:
            dtes = list_response.json().get('results', [])
            if dtes:
                dte_id = dtes[0]['id']
                
                # Obtener detalle
                response = requests.get(f"{BASE_URL}/sii/dtes/{dte_id}/", timeout=30)
                print(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    dte = response.json()
                    print(f"✅ Detalle del DTE {dte['folio']}:")
                    print(f"   Tipo: {dte['document_type_name']}")
                    print(f"   Cliente: {dte['recipient_name']}")
                    print(f"   Total: ${dte['total_amount']:,}")
                    print(f"   Track ID: {dte['sii_track_id']}")
                    print(f"   XML presente: {'Sí' if dte['xml_data'] else 'No'}")
                else:
                    print(f"❌ Error: {response.status_code}")
            else:
                print("⚠️ No hay DTEs disponibles para mostrar detalle")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def test_dtes_summary():
    """Test endpoint de resumen de DTEs"""
    print("\n📊 Probando endpoint de resumen de DTEs...")
    
    try:
        params = {
            'company_rut': '77794858',
            'fecha_desde': '2025-08-01',
            'fecha_hasta': '2025-08-31'
        }
        
        response = requests.get(f"{BASE_URL}/sii/dtes/summary/", params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            totals = data.get('totals', {})
            
            print(f"✅ Resumen de DTEs:")
            print(f"   Total Documentos: {totals.get('total_documents', 0)}")
            print(f"   Total Neto: ${totals.get('total_net_amount', 0):,}")
            print(f"   Total IVA: ${totals.get('total_tax_amount', 0):,}")
            print(f"   Total Bruto: ${totals.get('total_amount', 0):,}")
            
            print("\n   Por Tipo de Documento:")
            for tipo in data.get('by_document_type', []):
                print(f"     - {tipo['document_type_name']}: {tipo['count']} docs - ${tipo['total_amount']:,}")
            
            print("\n   Por Estado:")
            for estado in data.get('by_status', []):
                print(f"     - {estado['status_display']}: {estado['count']} docs - ${estado['total_amount']:,}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_sync_dtes():
    """Test endpoint de sincronización de DTEs"""
    print("\n🔄 Probando endpoint de sincronización de DTEs...")
    
    try:
        data = {
            'company_rut': '77794858',
            'company_dv': 'k',
            'fecha_desde': '2025-08-01',
            'fecha_hasta': '2025-08-31'
        }
        
        response = requests.post(f"{BASE_URL}/sii/dtes/sync/", 
                               json=data, 
                               timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Sincronización completada:")
            print(f"   Log ID: {result.get('sync_log_id')}")
            print(f"   Estado: {result.get('status')}")
            print(f"   Mensaje: {result.get('message')}")
            
            results = result.get('results', {})
            print(f"   Procesados: {results.get('processed', 0)}")
            print(f"   Creados: {results.get('created', 0)}")
            print(f"   Actualizados: {results.get('updated', 0)}")
            print(f"   Fallidos: {results.get('failed', 0)}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 INICIANDO PRUEBAS DE ENDPOINTS DE DTEs")
    print("=" * 60)
    
    # Ejecutar todas las pruebas
    test_list_dtes()
    test_list_dtes_with_filters()
    test_dte_detail()
    test_dtes_summary()
    test_sync_dtes()
    
    print("\n✅ PRUEBAS DE ENDPOINTS DE DTEs COMPLETADAS")