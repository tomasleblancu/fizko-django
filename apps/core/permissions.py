"""
Custom permissions for the Django application
"""
from rest_framework import permissions
from apps.accounts.models import UserRole


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Instance must have an attribute named `user` or `owner`.
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        return False


class IsCompanyMember(permissions.BasePermission):
    """
    Custom permission to check if user is a member of the company.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        company_id = request.headers.get('X-Company-ID')
        if not company_id:
            # Check if company_id is in URL or query params
            company_id = (view.kwargs.get('company_id') or 
                         request.query_params.get('company_id') or 
                         request.query_params.get('company'))
            if not company_id:
                return False

        return UserRole.objects.filter(
            user=request.user,
            company_id=company_id,
            active=True
        ).exists()

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # For Company objects, check if user has any role in this company
        if obj.__class__.__name__ == 'Company':
            return UserRole.objects.filter(
                user=request.user,
                company=obj,
                active=True
            ).exists()
        
        # Check if object has a company field
        if hasattr(obj, 'company'):
            return UserRole.objects.filter(
                user=request.user,
                company=obj.company,
                active=True
            ).exists()
        elif hasattr(obj, 'company_id'):
            return UserRole.objects.filter(
                user=request.user,
                company_id=obj.company_id,
                active=True
            ).exists()
        
        return False


class CanOnlyAccessOwnCompanies(permissions.BasePermission):
    """
    Permiso estricto que solo permite acceso a empresas donde el usuario tiene roles activos.
    Usado específicamente para el CompanyViewSet.
    """

    def has_permission(self, request, view):
        """
        Solo usuarios autenticados pueden acceder
        """
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """
        Solo permite acceso si el usuario tiene un rol activo en la empresa
        """
        if not request.user.is_authenticated:
            return False

        # Para objetos Company, verificar que el usuario tenga algún rol activo
        if obj.__class__.__name__ == 'Company':
            return UserRole.objects.filter(
                user=request.user,
                company=obj,
                active=True
            ).exists()
        
        return False


class IsCompanyOwner(IsCompanyMember):
    """
    Custom permission to check if user is an owner of the company.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        company_id = request.headers.get('X-Company-ID')
        if not company_id:
            company_id = (view.kwargs.get('company_id') or 
                         request.query_params.get('company_id') or 
                         request.query_params.get('company'))

        return UserRole.objects.filter(
            user=request.user,
            company_id=company_id,
            role__name='owner',
            active=True
        ).exists()

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        company_id = None
        if hasattr(obj, 'company'):
            company_id = obj.company.id
        elif hasattr(obj, 'company_id'):
            company_id = obj.company_id

        if company_id:
            return UserRole.objects.filter(
                user=request.user,
                company_id=company_id,
                role__name='owner',
                active=True
            ).exists()
        
        return False


class IsCompanyAdmin(IsCompanyMember):
    """
    Custom permission to check if user is an admin of the company.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        company_id = request.headers.get('X-Company-ID')
        if not company_id:
            company_id = (view.kwargs.get('company_id') or 
                         request.query_params.get('company_id') or 
                         request.query_params.get('company'))

        return UserRole.objects.filter(
            user=request.user,
            company_id=company_id,
            role__name__in=['owner', 'admin'],
            active=True
        ).exists()

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False

        company_id = None
        if hasattr(obj, 'company'):
            company_id = obj.company.id
        elif hasattr(obj, 'company_id'):
            company_id = obj.company_id

        if company_id:
            return UserRole.objects.filter(
                user=request.user,
                company_id=company_id,
                role__name__in=['owner', 'admin'],
                active=True
            ).exists()
        
        return False


class IsSameUserOrAdmin(permissions.BasePermission):
    """
    Permission to allow users to access their own data or admins to access any data.
    """

    def has_object_permission(self, request, view, obj):
        # Admin users can access any object
        if request.user.is_staff:
            return True

        # Users can access their own objects
        if hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class ReadOnlyOrAuthenticated(permissions.BasePermission):
    """
    Custom permission to allow read-only access to anyone,
    but require authentication for write operations.
    """

    def has_permission(self, request, view):
        return bool(
            request.method in permissions.SAFE_METHODS or
            request.user and request.user.is_authenticated
        )


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission to allow access only to verified users.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.is_verified
        )


class HasSIICredentials(permissions.BasePermission):
    """
    Permission to check if user's company has valid SII credentials.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        company_id = request.headers.get('X-Company-ID')
        if not company_id:
            company_id = (view.kwargs.get('company_id') or 
                         request.query_params.get('company_id') or 
                         request.query_params.get('company'))
            if not company_id:
                return False

        from apps.taxpayers.models import TaxpayerSiiCredentials
        return TaxpayerSiiCredentials.objects.filter(
            company_id=company_id,
            is_active=True
        ).exists()


class IsTaskOwner(permissions.BasePermission):
    """
    Permission to check if user owns the task.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Check if user created the task or is assigned to it
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user.email
        elif hasattr(obj, 'assigned_to'):
            return obj.assigned_to == request.user.email or obj.created_by == request.user.email
        
        return False