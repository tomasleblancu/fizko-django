from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView, UserViewSet, UserProfileViewSet,
    RoleViewSet, UserRoleViewSet, CurrentUserView, debug_user_permissions,
    VerificationView, SendVerificationCodeView, ResendVerificationCodeView,
    verification_status
)

app_name = 'accounts'

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('profiles', UserProfileViewSet, basename='profiles')
router.register('roles', RoleViewSet, basename='roles')
router.register('user-roles', UserRoleViewSet, basename='user-roles')

urlpatterns = [
    # Authentication endpoints
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserView.as_view(), name='current_user'),

    # Verification endpoints
    path('verification/verify/', VerificationView.as_view(), name='verify_code'),
    path('verification/send/', SendVerificationCodeView.as_view(), name='send_verification_code'),
    path('verification/resend/', ResendVerificationCodeView.as_view(), name='resend_verification_code'),
    path('verification/status/', verification_status, name='verification_status'),

    # Debug endpoints
    path('debug/permissions/', debug_user_permissions, name='debug_permissions'),

    # Router URLs
    path('', include(router.urls)),
]
