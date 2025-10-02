"""
URL configuration for processes management interface
"""
from django.urls import path
from . import views

app_name = 'processes'

urlpatterns = [
    # ============================================================================
    # DASHBOARD
    # ============================================================================

    path('', views.processes_dashboard, name='dashboard'),
    path('dashboard/', views.processes_dashboard, name='dashboard'),

    # ============================================================================
    # PLANTILLAS DE PROCESOS
    # ============================================================================

    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:template_id>/', views.template_detail, name='template_detail'),
    path('templates/<int:template_id>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:template_id>/toggle/', views.toggle_template_status, name='toggle_template_status'),

    # ============================================================================
    # TAREAS DE PLANTILLAS
    # ============================================================================

    path('templates/<int:template_id>/tasks/create/', views.task_create, name='task_create'),
    path('templates/<int:template_id>/tasks/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('templates/<int:template_id>/tasks/<int:task_id>/delete/', views.task_delete, name='task_delete'),

    # ============================================================================
    # SEGMENTOS DE EMPRESAS
    # ============================================================================

    path('segments/', views.segment_list, name='segment_list'),
    path('segments/create/', views.segment_create, name='segment_create'),
    path('segments/<int:segment_id>/', views.segment_detail, name='segment_detail'),
    path('segments/<int:segment_id>/edit/', views.segment_edit, name='segment_edit'),

    # ============================================================================
    # REGLAS DE ASIGNACIÓN
    # ============================================================================

    path('rules/', views.rule_list, name='rule_list'),
    path('rules/<int:rule_id>/', views.rule_detail, name='rule_detail'),
    path('rules/<int:rule_id>/toggle/', views.toggle_rule_status, name='toggle_rule_status'),
]
