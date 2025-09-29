from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, Role, UserRole, TeamInvitation


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_verified', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone', 'is_verified')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('email', 'phone', 'is_verified')
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'position', 'phone')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'position')
    list_filter = ('created_at',)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'company', 'active', 'created_at')
    list_filter = ('role', 'active', 'created_at')
    search_fields = ('user__email', 'role__name', 'company__name')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'role', 'company')


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'status', 'get_companies', 'role', 'invited_by', 'expires_at', 'created_at')
    list_filter = ('status', 'role', 'created_at', 'expires_at')
    search_fields = ('email', 'invited_by__email', 'role__name')
    readonly_fields = ('token', 'created_at', 'updated_at')
    filter_horizontal = ('companies',)

    def get_companies(self, obj):
        return ", ".join([company.display_name for company in obj.companies.all()])
    get_companies.short_description = 'Companies'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'role', 'invited_by'
        ).prefetch_related('companies')