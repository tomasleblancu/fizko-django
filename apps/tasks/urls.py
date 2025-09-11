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

urlpatterns = [
    path('', include(router.urls)),
]
