from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TaxFormViewSet, TaxFormTemplateViewSet, forms_summary

app_name = 'forms'

router = DefaultRouter()
router.register('tax-forms', TaxFormViewSet, basename='taxform')
router.register('templates', TaxFormTemplateViewSet, basename='taxformtemplate')

urlpatterns = [
    path('', include(router.urls)),
    path('summary/', forms_summary, name='forms_summary'),
]
