from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'hr'

router = DefaultRouter()
router.register('employees', views.EmployeeViewSet, basename='employee')
router.register('contracts', views.EmployeeContractViewSet, basename='contract')

urlpatterns = [
    path('', include(router.urls)),
]