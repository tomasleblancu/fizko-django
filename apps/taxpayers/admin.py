from django.contrib import admin
from .models import TaxPayer, TaxpayerActivity, TaxpayerAddress, TaxpayerPartner, TaxpayerRepresentative, TaxpayerStamp, TaxpayerSiiCredentials


@admin.register(TaxPayer)
class TaxPayerAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'tax_id', 'tipo_contribuyente', 'estado', 'is_verified', 'last_sii_sync', 'created_at')
    list_filter = ('estado', 'tipo_contribuyente', 'is_verified', 'is_active', 'data_source', 'created_at')
    search_fields = ('razon_social', 'nombre', 'tax_id', 'rut', 'email')
    readonly_fields = ('full_rut', 'is_persona_juridica', 'formatted_address', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('tax_id', 'rut', 'dv', 'full_rut')
        }),
        ('Datos del Contribuyente', {
            'fields': ('razon_social', 'nombre', 'tipo_contribuyente', 'estado', 'is_persona_juridica')
        }),
        ('Actividad Económica', {
            'fields': ('actividad_description', 'glosa_actividad', 'fecha_inicio_actividades')
        }),
        ('Ubicación', {
            'fields': ('direccion', 'comuna', 'region', 'formatted_address')
        }),
        ('Contacto', {
            'fields': ('email', 'mobile_phone')
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
            # Todos los campos del SII son readonly al editar
            readonly.extend(['tax_id', 'rut', 'dv', 'razon_social', 'nombre', 'tipo_contribuyente', 
                           'actividad_description', 'glosa_actividad', 'fecha_inicio_actividades',
                           'direccion', 'comuna', 'region', 'email', 'mobile_phone'])
        return readonly


@admin.register(TaxpayerActivity)
class TaxpayerActivityAdmin(admin.ModelAdmin):
    list_display = ('company', 'code', 'description', 'category', 'subcategory', 'is_active')
    list_filter = ('category', 'subcategory', 'is_active')
    search_fields = ('company__business_name', 'company__tax_id', 'code', 'description', 'category')
    raw_id_fields = ('company',)


@admin.register(TaxpayerAddress)
class TaxpayerAddressAdmin(admin.ModelAdmin):
    list_display = ('company', 'address_type', 'city', 'region', 'is_primary', 'is_active')
    list_filter = ('address_type', 'region', 'is_primary', 'is_active')
    search_fields = ('company__business_name', 'company__tax_id', 'street_address', 'city')
    raw_id_fields = ('company',)


@admin.register(TaxpayerPartner)
class TaxpayerPartnerAdmin(admin.ModelAdmin):
    list_display = ('company', 'partner_name', 'partner_type', 'ownership_percentage', 'is_active')
    list_filter = ('partner_type', 'is_active')
    search_fields = ('company__business_name', 'company__tax_id', 'partner_rut', 'partner_name')
    raw_id_fields = ('company',)


@admin.register(TaxpayerRepresentative)
class TaxpayerRepresentativeAdmin(admin.ModelAdmin):
    list_display = ('company', 'representative_name', 'position', 'is_valid', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('company__business_name', 'company__tax_id', 'representative_rut', 'representative_name')
    raw_id_fields = ('company',)


@admin.register(TaxpayerStamp)
class TaxpayerStampAdmin(admin.ModelAdmin):
    list_display = ('company', 'stamp_id', 'stamp_type', 'valid_until', 'is_valid', 'is_active')
    list_filter = ('stamp_type', 'is_active')
    search_fields = ('company__business_name', 'company__tax_id', 'stamp_id', 'certificate_serial')
    raw_id_fields = ('company',)


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