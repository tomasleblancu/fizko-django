from django.contrib import admin
from .models import Company


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
