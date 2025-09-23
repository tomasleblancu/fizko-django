from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health_check, sii_status, sii_auth_status,
    consultar_contribuyente, verificar_credenciales,
    list_sii_dtes, get_dte_detail, get_dtes_summary, sync_dtes_from_sii,
    sync_company_dtes, test_sii_connection, get_sync_history, sync_taxpayer_info
)
# Importar views F29 de manera modular
from .views.f29 import obtener_formulario_f29, listar_codigos_f29, health_f29, buscar_formularios_f29

app_name = 'sii'

router = DefaultRouter()

urlpatterns = [
    # Health checks
    path('health/', health_check, name='health'),
    path('status/', sii_status, name='status'),
    
    # Main SII endpoints
    path('contribuyente/', consultar_contribuyente, name='consultar_contribuyente'),
    path('verificar-credenciales/', verificar_credenciales, name='verificar_credenciales'),
    path('auth-status/<int:company_id>/', sii_auth_status, name='sii_auth_status'),
    
    # Sync endpoints
    path('sync-dtes/', sync_company_dtes, name='sync_company_dtes'),
    path('test-connection/', test_sii_connection, name='test_sii_connection'),
    path('sync-taxpayer/', sync_taxpayer_info, name='sync_taxpayer_info'),
    path('sync-history/<int:company_id>/', get_sync_history, name='get_sync_history'),
    
    # DTEs endpoints
    path('dtes/', list_sii_dtes, name='list_dtes'),
    path('dtes/<int:dte_id>/', get_dte_detail, name='get_dte_detail'),
    path('dtes/summary/', get_dtes_summary, name='get_dtes_summary'),
    path('dtes/sync/', sync_dtes_from_sii, name='sync_dtes'),

    # F29 endpoints (modular addition)
    path('f29/formulario/', obtener_formulario_f29, name='obtener_formulario_f29'),
    path('f29/buscar/', buscar_formularios_f29, name='buscar_formularios_f29'),
    path('f29/codigos/', listar_codigos_f29, name='listar_codigos_f29'),
    path('f29/health/', health_f29, name='health_f29'),

    # Router URLs
    path('', include(router.urls)),
]
