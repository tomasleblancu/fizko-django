from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'tasks'

# El frontend hace POST a /api/v1/tasks/ directamente, así que registrar en la raíz
router = DefaultRouter()
router.register('', views.TaskViewSet, basename='task')  # En la raíz
router.register('categories', views.TaskCategoryViewSet, basename='task-category')
router.register('comments', views.TaskCommentViewSet, basename='task-comment')
router.register('attachments', views.TaskAttachmentViewSet, basename='task-attachment')
router.register('logs', views.TaskLogViewSet, basename='task-log')

# Endpoints para procesos
router.register('processes', views.ProcessViewSet, basename='process')
router.register('process-templates', views.ProcessTemplateViewSet, basename='process-template')
router.register('process-tasks', views.ProcessTaskViewSet, basename='process-task')
router.register('process-executions', views.ProcessExecutionViewSet, basename='process-execution')

urlpatterns = [
    path('', include(router.urls)),
]
