from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'analytics'

router = DefaultRouter()
# router.register('endpoint', ViewSet, basename='endpoint')

urlpatterns = [
    path('', include(router.urls)),
]
