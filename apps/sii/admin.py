from django.contrib import admin
from .models import SIISession, SIISyncLog


@admin.register(SIISession)
class SIISessionAdmin(admin.ModelAdmin):
    list_display = ('company_rut', 'company_dv', 'username', 'is_active', 'expires_at', 'last_activity')
    list_filter = ('is_active', 'expires_at', 'created_at')
    search_fields = ('company_rut', 'username', 'session_id')
    readonly_fields = ('is_expired', 'last_activity', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Empresa', {
            'fields': ('company_rut', 'company_dv', 'username')
        }),
        ('Sesión', {
            'fields': ('session_id', 'session_token', 'cookies_data')
        }),
        ('Estado', {
            'fields': ('is_active', 'expires_at', 'is_expired', 'last_activity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )








@admin.register(SIISyncLog)
class SIISyncLogAdmin(admin.ModelAdmin):
    list_display = ('company_rut', 'company_dv', 'sync_type', 'status', 'started_at', 'completed_at', 'records_processed', 'success_rate')
    list_filter = ('sync_type', 'status', 'started_at')
    search_fields = ('company_rut', 'sync_type')
    readonly_fields = ('duration', 'success_rate', 'started_at')
    
    fieldsets = (
        ('Empresa', {
            'fields': ('company_rut', 'company_dv')
        }),
        ('Sincronización', {
            'fields': ('sync_type', 'status', 'started_at', 'completed_at', 'duration')
        }),
        ('Estadísticas', {
            'fields': ('records_processed', 'records_created', 'records_updated', 'records_failed', 'success_rate')
        }),
        ('Error', {
            'fields': ('error_message',)
        }),
        ('Datos', {
            'fields': ('sync_data',),
            'classes': ('collapse',)
        })
    )
