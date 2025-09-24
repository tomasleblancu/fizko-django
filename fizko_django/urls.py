"""
URL configuration for fizko_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse({'status': 'ok', 'service': 'fizko-django'})

# Main URL patterns
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Health check
    path('health/', health_check, name='health-check'),
    
    # API v1 endpoints
    path('api/v1/', include([
        path('auth/', include('apps.accounts.urls')),
        path('companies/', include('apps.companies.urls')),
        path('taxpayers/', include('apps.taxpayers.urls')),
        path('sii/', include('apps.sii.urls')),
        path('documents/', include('apps.documents.urls')),
        path('expenses/', include('apps.expenses.urls')),
        path('forms/', include('apps.forms.urls')),
        path('analytics/', include('apps.analytics.urls')),
        path('ai/', include('apps.ai_assistant.urls')),
        path('tasks/', include('apps.tasks.urls')),
        path('notifications/', include('apps.notifications.urls')),
        path('rates/', include('apps.rates.urls')),
        path('onboarding/', include('apps.onboarding.urls')),
        # path('chat/', include('apps.chat.urls')),  # TEMP: Deshabilitado
    ])),
    
    # DRF browsable API (for development)
    path('api-auth/', include('rest_framework.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Simple health endpoint is already configured above at /health/

# Admin site customization
admin.site.site_header = 'Fizko Administration'
admin.site.site_title = 'Fizko Admin'
admin.site.index_title = 'Fizko Management'