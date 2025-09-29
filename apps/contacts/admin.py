from django.contrib import admin
from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """
    Configuración del admin para Contact
    """
    list_display = [
        'tax_id',
        'name',
        'company',
        'role_display',
        'category',
        'is_active',
        'created_at',
    ]

    list_filter = [
        'is_client',
        'is_provider',
        'is_active',
        'category',
        'company',
        'created_at',
    ]

    search_fields = [
        'tax_id',
        'name',
        'email',
        'phone',
        'category',
        'notes',
    ]

    readonly_fields = [
        'role_display',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Información Básica', {
            'fields': ('tax_id', 'name', 'company')
        }),
        ('Roles', {
            'fields': ('is_client', 'is_provider', 'role_display')
        }),
        ('Información de Contacto', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Detalles Adicionales', {
            'fields': ('category', 'notes', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    ordering = ['-created_at']

    def get_queryset(self, request):
        """
        Optimizar queries para el admin
        """
        return super().get_queryset(request).select_related('company')

    def has_module_permission(self, request):
        """
        Solo usuarios staff pueden acceder al módulo
        """
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        """
        Permisos de visualización
        """
        return request.user.is_staff

    def has_add_permission(self, request):
        """
        Permisos de creación
        """
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        """
        Permisos de modificación
        """
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        """
        Permisos de eliminación - solo superusuarios
        """
        return request.user.is_superuser
