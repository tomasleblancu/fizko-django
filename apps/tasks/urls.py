from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'tasks'

# Endpoints para procesos (registrar primero para evitar conflictos)
router = DefaultRouter()
router.register('processes', views.ProcessViewSet, basename='process')
router.register('process-templates', views.ProcessTemplateViewSet, basename='process-template')
router.register('process-tasks', views.ProcessTaskViewSet, basename='process-task')
router.register('process-executions', views.ProcessExecutionViewSet, basename='process-execution')

# Endpoints para tareas individuales
router.register('tasks', views.TaskViewSet, basename='task')  # Cambiar de raíz a 'tasks'
router.register('categories', views.TaskCategoryViewSet, basename='task-category')
router.register('comments', views.TaskCommentViewSet, basename='task-comment')
router.register('attachments', views.TaskAttachmentViewSet, basename='task-attachment')
router.register('logs', views.TaskLogViewSet, basename='task-log')

urlpatterns = [
    path('', include(router.urls)),
]
