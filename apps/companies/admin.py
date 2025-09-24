from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Company, BackgroundTaskTracker


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_id', 'email', 'is_active', 'electronic_biller', 'is_verified_with_sii', 'created_at')
    list_filter = ('is_active', 'electronic_biller', 'person_company', 'preferred_currency', 'created_at')
    search_fields = ('business_name', 'display_name', 'tax_id', 'email', 'taxpayer__razon_social')
    readonly_fields = ('full_rut', 'razon_social', 'sii_address', 'activity_description', 'is_verified_with_sii', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('taxpayer', 'tax_id', 'full_rut', 'razon_social')
        }),
        ('Configuración de Usuario', {
            'fields': ('business_name', 'display_name', 'person_company')
        }),
        ('Contacto', {
            'fields': ('email', 'billing_email', 'accounting_email', 'mobile_phone', 'website')
        }),
        ('Información del SII (Solo Lectura)', {
            'fields': ('sii_address', 'activity_description', 'is_verified_with_sii'),
            'classes': ('collapse',)
        }),
        ('Configuración de Aplicación', {
            'fields': ('electronic_biller', 'preferred_currency', 'time_zone')
        }),
        ('Notificaciones', {
            'fields': ('notify_new_documents', 'notify_tax_deadlines', 'notify_system_updates'),
            'classes': ('collapse',)
        }),
        ('Estado y Configuración', {
            'fields': ('is_active', 'login_tries', 'logo')
        }),
        ('Metadatos', {
            'fields': ('record_created_at', 'record_updated_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # editing an existing object
            readonly.extend(['taxpayer', 'tax_id'])
        return readonly


@admin.register(BackgroundTaskTracker)
class BackgroundTaskTrackerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'company_link', 'colored_status', 'progress_bar', 'started_at_display', 'duration_display')
    list_filter = ('status', 'task_name', 'company', 'created_at')
    search_fields = ('display_name', 'company__business_name', 'company__display_name', 'task_id')
    readonly_fields = ('task_id', 'is_active', 'is_completed', 'duration_display', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 25
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')

    def company_link(self, obj):
        """Link to the company admin page"""
        url = f"/admin/companies/company/{obj.company.id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.company.name)
    company_link.short_description = 'Empresa'

    def colored_status(self, obj):
        """Status with color coding"""
        colors = {
            'pending': '#ffa500',  # Orange
            'running': '#0066cc',  # Blue
            'success': '#28a745',  # Green
            'failed': '#dc3545'    # Red
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    colored_status.short_description = 'Estado'

    def progress_bar(self, obj):
        """Visual progress bar"""
        if obj.status == 'running' and obj.progress > 0:
            return format_html(
                '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
                '<div style="width: {}%; height: 20px; background-color: #007bff; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
                '{}%</div></div>',
                obj.progress, obj.progress
            )
        return f"{obj.progress}%"
    progress_bar.short_description = 'Progreso'

    def started_at_display(self, obj):
        """Formatted start time"""
        if obj.started_at:
            return obj.started_at.strftime('%d/%m/%Y %H:%M')
        return '-'
    started_at_display.short_description = 'Iniciado'

    def duration_display(self, obj):
        """Human readable duration"""
        if obj.duration:
            total_seconds = int(obj.duration.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        elif obj.started_at and obj.status == 'running':
            # Calculate current duration for running tasks
            current_duration = timezone.now() - obj.started_at
            total_seconds = int(current_duration.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            if minutes > 0:
                return f"{minutes}m {seconds}s (ejecutándose)"
            return f"{seconds}s (ejecutándose)"
        return '-'
    duration_display.short_description = 'Duración'

    fieldsets = (
        ('Información de la Tarea', {
            'fields': ('display_name', 'task_name', 'company', 'task_id')
        }),
        ('Estado y Progreso', {
            'fields': ('status', 'progress', 'is_active', 'is_completed')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration_display'),
            'classes': ('collapse',)
        }),
        ('Detalles Técnicos', {
            'fields': ('error_message', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Metadatos del Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['cleanup_completed_tasks']

    def cleanup_completed_tasks(self, request, queryset):
        """Action to clean up completed tasks"""
        completed_tasks = queryset.filter(status__in=['success', 'failed'])
        count = completed_tasks.count()
        completed_tasks.delete()
        self.message_user(request, f'{count} tareas completadas eliminadas.')
    cleanup_completed_tasks.short_description = 'Eliminar tareas completadas seleccionadas'
