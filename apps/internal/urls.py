"""
URLs para la app internal - Interfaces administrativas internas
"""
from django.urls import path, include

app_name = 'internal'

urlpatterns = [
    # Dashboard principal
    path('', lambda request: __import__('django.shortcuts').shortcuts.render(request, 'internal/dashboard.html'), name='dashboard'),

    # Sección de Chat (Agentes)
    path('chat/', include('apps.internal.views.chat.urls', namespace='chat')),

    # Sección de Procesos
    path('processes/', include('apps.internal.views.processes.urls', namespace='processes')),
]
