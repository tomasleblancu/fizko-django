from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'companies'

router = DefaultRouter()
router.register(r'', views.CompanyViewSet, basename='companies')

urlpatterns = [
    # Endpoint integrado para crear compañía con datos SII
    path('create-with-sii/', views.create_company_with_sii_data, name='create-with-sii'),
    # Endpoint para actualizar credenciales SII de empresa existente
    path('update-sii-credentials/', views.update_sii_credentials, name='update-sii-credentials'),
    
    # Vista de prueba temporal
    path('test-creation/', views.test_company_creation, name='test-creation'),
    path('test-credentials/', views.test_credentials_validation, name='test-credentials'),
    path('test-credentials-storage/', views.test_credentials_storage, name='test-credentials-storage'),
    path('test-sync-stored-credentials/', views.test_sync_with_stored_credentials, name='test-sync-stored-credentials'),
    path('test-logout/', views.test_logout_flow, name='test-logout'),
    path('test-sii-integration/', views.test_create_with_sii_no_auth, name='test-sii-integration'),
    path('test-force-real-sii/', views.test_force_real_sii, name='test-force-real-sii'),
    
    # Router URLs (CRUD básico de compañías)
    path('', include(router.urls)),
]
