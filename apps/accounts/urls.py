from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView, UserViewSet, UserProfileViewSet,
    RoleViewSet, UserRoleViewSet, CurrentUserView, debug_user_permissions
)

app_name = 'accounts'

router = DefaultRouter()
router.register('users', UserViewSet, basename='users')
router.register('profiles', UserProfileViewSet, basename='profiles')
router.register('roles', RoleViewSet, basename='roles')
router.register('user-roles', UserRoleViewSet, basename='user-roles')

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserView.as_view(), name='current_user'),

    # Debug endpoints
    path('debug/permissions/', debug_user_permissions, name='debug_permissions'),

    # Router URLs
    path('', include(router.urls)),
]
