#!/usr/bin/env python
"""
Test endpoint para probar obtención de documentos del SII via API
"""
import requests
import json

# URL base del API
BASE_URL = "http://localhost:8000/api/v1"

def test_sii_contributor():
    """Test endpoint de consulta de contribuyente"""
    print("🔍 Probando endpoint de consulta de contribuyente...")
    
    # RUT de prueba
    rut = "77794858-k"
    
    try:
        response = requests.get(f"{BASE_URL}/sii/contribuyente/", 
                              params={"rut": rut}, 
                              timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            data = response_data.get('data', {})  # Los datos están dentro de 'data'
            print("✅ Contribuyente consultado exitosamente:")
            print(f"   - RUT: {data.get('rut', 'N/A')}")
            print(f"   - Razón Social: {data.get('razon_social', 'N/A')}")
            print(f"   - Estado: {data.get('estado', 'N/A')}")
            print(f"   - Dirección: {data.get('direccion', 'N/A')}")
            print(f"   - Status: {response_data.get('status', 'N/A')}")
            print(f"   - Method: {response_data.get('authentication_method', 'N/A')}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error al hacer request: {e}")

def test_document_sync():
    """Test endpoint de sincronización de documentos (si existe)"""
    print("\n📄 Probando endpoints de documentos...")
    
    try:
        # Probar endpoint de documentos
        response = requests.get(f"{BASE_URL}/documents/", timeout=30)
        print(f"Documentos endpoint - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Total documentos: {data.get('count', 0)}")
        
        # Probar endpoint de resumen financiero
        params = {
            "company_id": 24,
            "start_date": "2025-08-01",
            "end_date": "2025-08-31"
        }
        response = requests.get(f"{BASE_URL}/documents/financial_summary/", 
                              params=params, timeout=30)
        
        print(f"Resumen financiero - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Resumen financiero obtenido:")
            print(f"   - Ventas: ${data.get('ventas', {}).get('total', 0):,}")
            print(f"   - Compras: ${data.get('compras', {}).get('total', 0):,}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_companies():
    """Test endpoint de empresas"""
    print("\n🏢 Probando endpoint de empresas...")
    
    try:
        response = requests.get(f"{BASE_URL}/companies/", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            companies = data.get('results', [])
            print(f"✅ Empresas encontradas: {len(companies)}")
            
            for company in companies[:2]:  # Mostrar solo las primeras 2
                print(f"   - {company.get('name', 'N/A')} ({company.get('tax_id', 'N/A')})")
        else:
            print(f"❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_sii_status():
    """Test endpoint de estado SII"""
    print("\n🔐 Probando estado de SII...")
    
    try:
        # Probar con company_id conocido
        response = requests.get(f"{BASE_URL}/sii/auth-status/24/", timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Estado SII:")
            print(f"   - Integrado: {data.get('integrated', False)}")
            print(f"   - Credenciales válidas: {data.get('credentials_valid', False)}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text[:200])
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 INICIANDO PRUEBAS DE ENDPOINTS SII")
    print("=" * 60)
    
    # Ejecutar todas las pruebas
    test_companies()
    test_sii_contributor()
    test_document_sync()
    test_sii_status()
    
    print("\n✅ PRUEBAS DE ENDPOINTS COMPLETADAS")