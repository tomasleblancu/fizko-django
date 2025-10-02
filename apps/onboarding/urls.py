from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OnboardingStepViewSet, UserOnboardingViewSet, test_onboarding_company_integration
# OnboardingProgressViewSet temporalmente deshabilitado

app_name = 'onboarding'

router = DefaultRouter()
router.register('steps', OnboardingStepViewSet, basename='onboarding-steps')
router.register('user', UserOnboardingViewSet, basename='user-onboarding')
# router.register('progress', OnboardingProgressViewSet, basename='onboarding-progress')  # Disabled

urlpatterns = [
    path('test-company-integration/', test_onboarding_company_integration, name='test-company-integration'),
    path('', include(router.urls)),
]
