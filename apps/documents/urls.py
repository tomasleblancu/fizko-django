from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'documents'

router = DefaultRouter()
router.register('', views.DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
    path('auth-debug/', views.auth_debug, name='auth-debug'),  # Endpoint temporal de debug
    path('debug-dates/', views.debug_frontend_dates, name='debug-dates'),  # Debug fechas frontend
]
