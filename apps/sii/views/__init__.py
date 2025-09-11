"""
Módulo de views modular para la integración SII
Estructura organizada por funcionalidad para mejor mantenibilidad
"""

# Health checks y status
from .health import health_check, sii_status, sii_auth_status

# Consultas de contribuyente
from .contributor import consultar_contribuyente

# Verificación de credenciales
from .credentials import verificar_credenciales

# Gestión de documentos (DTEs)
from .documents import (
    list_sii_dtes,
    get_dte_detail, 
    get_dtes_summary,
    sync_dtes_from_sii
)

# Sincronización
from .sync import sync_company_dtes, sync_taxpayer_info, get_sync_history, test_sii_connection

__all__ = [
    # Health & Status
    'health_check',
    'sii_status', 
    'sii_auth_status',
    
    # Contributor
    'consultar_contribuyente',
    
    # Credentials
    'verificar_credenciales',
    
    # Documents
    'list_sii_dtes',
    'get_dte_detail',
    'get_dtes_summary', 
    'sync_dtes_from_sii',
    
    # Sync
    'sync_company_dtes',
    'sync_taxpayer_info', 
    'get_sync_history',
    'test_sii_connection'
]