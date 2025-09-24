from django.contrib import admin
from django import forms
from .models import TaxPayer, TaxpayerSiiCredentials


class TaxPayerAdminForm(forms.ModelForm):
    """Formulario personalizado para TaxPayer con checkboxes para procesos"""
    f29_monthly = forms.BooleanField(label='F29 Mensual', required=False,
                                     help_text='Declaración mensual de IVA')
    f22_annual = forms.BooleanField(label='F22 Anual', required=False,
                                    help_text='Declaración anual de renta')
    f3323_quarterly = forms.BooleanField(label='F3323 Trimestral', required=False,
                                         help_text='Declaración trimestral simplificada')
    document_sync = forms.BooleanField(label='Sincronización de Documentos', required=False,
                                       help_text='Sincronización automática de DTEs')
    sii_integration = forms.BooleanField(label='Integración SII', required=False,
                                         help_text='Integración completa con SII')

    class Meta:
        model = TaxPayer
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Cargar valores actuales de setting_procesos
            settings = self.instance.get_process_settings()
            self.fields['f29_monthly'].initial = settings.get('f29_monthly', False)
            self.fields['f22_annual'].initial = settings.get('f22_annual', False)
            self.fields['f3323_quarterly'].initial = settings.get('f3323_quarterly', False)
            self.fields['document_sync'].initial = settings.get('document_sync', True)
            self.fields['sii_integration'].initial = settings.get('sii_integration', True)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Actualizar setting_procesos con los valores del formulario
        instance.setting_procesos = {
            'f29_monthly': self.cleaned_data.get('f29_monthly', False),
            'f22_annual': self.cleaned_data.get('f22_annual', False),
            'f3323_quarterly': self.cleaned_data.get('f3323_quarterly', False),
            'document_sync': self.cleaned_data.get('document_sync', True),
            'sii_integration': self.cleaned_data.get('sii_integration', True),
        }

        if commit:
            instance.save()
        return instance


@admin.register(TaxPayer)
class TaxPayerAdmin(admin.ModelAdmin):
    form = TaxPayerAdminForm
    list_display = ('tax_id', 'display_razon_social', 'company', 'display_processes', 'is_verified', 'last_sii_sync')
    list_display_links = ('tax_id', 'display_razon_social')
    list_filter = ('is_verified', 'is_active', 'data_source', 'created_at')
    search_fields = ('razon_social', 'tax_id', 'rut', 'company__display_name', 'company__business_name')
    readonly_fields = ('full_rut', 'created_at', 'updated_at', 'formatted_settings')

    def display_razon_social(self, obj):
        """Muestra la razón social o un placeholder si está vacío"""
        return obj.razon_social or f"(Sin razón social)"
    display_razon_social.short_description = "Razón Social"

    def display_processes(self, obj):
        """Muestra los procesos activos de forma resumida"""
        if not obj.setting_procesos:
            return "Sin configurar"

        active = []
        settings = obj.get_process_settings()

        if settings.get('f29_monthly'): active.append('F29')
        if settings.get('f22_annual'): active.append('F22')
        if settings.get('f3323_quarterly'): active.append('F3323')
        if settings.get('document_sync'): active.append('Docs')
        if settings.get('sii_integration'): active.append('SII')

        return ', '.join(active) if active else 'Ninguno'
    display_processes.short_description = "Procesos Activos"

    def formatted_settings(self, obj):
        """Muestra la configuración de procesos de forma legible"""
        if not obj.setting_procesos:
            return "No configurado"

        settings = obj.get_process_settings()
        lines = []

        lines.append("✅ Procesos Habilitados:")
        if settings.get('f29_monthly'): lines.append("  • F29 Mensual")
        if settings.get('f22_annual'): lines.append("  • F22 Anual")
        if settings.get('f3323_quarterly'): lines.append("  • F3323 Trimestral")
        if settings.get('document_sync'): lines.append("  • Sincronización de Documentos")
        if settings.get('sii_integration'): lines.append("  • Integración SII")

        lines.append("\n❌ Procesos Deshabilitados:")
        if not settings.get('f29_monthly'): lines.append("  • F29 Mensual")
        if not settings.get('f22_annual'): lines.append("  • F22 Anual")
        if not settings.get('f3323_quarterly'): lines.append("  • F3323 Trimestral")
        if not settings.get('document_sync'): lines.append("  • Sincronización de Documentos")
        if not settings.get('sii_integration'): lines.append("  • Integración SII")

        return '\n'.join(lines)
    formatted_settings.short_description = "Configuración de Procesos"

    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'tax_id', 'rut', 'dv', 'full_rut')
        }),
        ('Datos del Contribuyente', {
            'fields': ('razon_social',)
        }),
        ('Configuración de Procesos Tributarios', {
            'fields': ('f29_monthly', 'f22_annual', 'f3323_quarterly', 'document_sync', 'sii_integration', 'formatted_settings'),
            'description': 'Seleccione los procesos tributarios que debe gestionar este contribuyente'
        }),
        ('Metadatos de Extracción', {
            'fields': ('data_source', 'last_sii_sync', 'is_verified', 'sii_raw_data'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # editing an existing object
            # Los campos del SII son readonly al editar
            readonly.extend(['tax_id', 'rut', 'dv', 'razon_social'])
        return readonly




@admin.register(TaxpayerSiiCredentials)
class TaxpayerSiiCredentialsAdmin(admin.ModelAdmin):
    list_display = ('tax_id', 'company', 'user', 'is_active', 'is_credentials_valid', 'verification_failures', 'last_verified', 'created_at')
    list_filter = ('is_active', 'verification_failures', 'created_at', 'last_verified')
    search_fields = ('tax_id', 'company__business_name', 'company__display_name', 'user__username', 'user__email')
    readonly_fields = ('is_credentials_valid', 'encrypted_password_info', 'created_at', 'updated_at')
    raw_id_fields = ('company', 'user')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('tax_id', 'company', 'user')
        }),
        ('Estado de Credenciales', {
            'fields': ('is_active', 'is_credentials_valid', 'verification_failures', 'last_verified')
        }),
        ('Información Técnica', {
            'fields': ('encrypted_password_info', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def encrypted_password_info(self, obj):
        """Muestra información sobre la contraseña encriptada sin exponerla"""
        if obj and obj.encrypted_password:
            return f"Contraseña encriptada ({len(obj.encrypted_password)} caracteres) - Encriptación: Fernet"
        return "No hay contraseña almacenada"
    encrypted_password_info.short_description = "Estado de Encriptación"
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:  # editing an existing object
            # No permitir cambiar los campos críticos al editar
            readonly.extend(['tax_id', 'company', 'user'])
        return readonly
    
    def has_change_permission(self, request, obj=None):
        """Permitir cambios limitados (solo estado y fallos)"""
        return request.user.is_superuser or request.user.has_perm('taxpayers.change_taxpayersiicredentials')
    
    def has_delete_permission(self, request, obj=None):
        """Solo superusuarios pueden eliminar credenciales"""
        return request.user.is_superuser
    
    actions = ['mark_as_inactive', 'reset_verification_failures']
    
    def mark_as_inactive(self, request, queryset):
        """Marcar credenciales como inactivas"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} credenciales marcadas como inactivas.')
    mark_as_inactive.short_description = "Marcar como inactivas"
    
    def reset_verification_failures(self, request, queryset):
        """Resetear contador de fallos de verificación"""
        updated = queryset.update(verification_failures=0)
        self.message_user(request, f'Fallos de verificación reseteados para {updated} credenciales.')
    reset_verification_failures.short_description = "Resetear fallos de verificación"