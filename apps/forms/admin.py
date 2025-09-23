from django.contrib import admin
from .models import TaxFormTemplate, TaxForm, TaxFormField, TaxFormPayment, TaxFormAuditLog


@admin.register(TaxFormTemplate)
class TaxFormTemplateAdmin(admin.ModelAdmin):
    list_display = ('form_code', 'name', 'form_type', 'version', 'is_active')
    list_filter = ('form_type', 'is_active', 'created_at')
    search_fields = ('form_code', 'name', 'description')
    ordering = ('form_code',)


@admin.register(TaxForm)
class TaxFormAdmin(admin.ModelAdmin):
    list_display = ('get_company_display', 'template', 'tax_period', 'status', 'total_tax_due', 'sii_folio', 'get_details_status', 'is_overdue')
    list_filter = ('template', 'status', 'tax_year', 'due_date', 'company', 'details_extracted')
    search_fields = ('company__business_name', 'company__tax_id', 'company_rut', 'sii_folio')
    readonly_fields = ('is_overdue', 'balance_due', 'needs_detail_extraction', 'has_recent_details')
    list_select_related = ('company', 'template')

    fieldsets = (
        ('Empresa', {
            'fields': ('company', 'company_rut', 'company_dv', 'template'),
            'description': 'company es la referencia principal, company_rut/company_dv son campos legacy'
        }),
        ('Período', {
            'fields': ('tax_year', 'tax_month', 'tax_period')
        }),
        ('Estado', {
            'fields': ('status', 'due_date', 'submission_date', 'is_overdue')
        }),
        ('Datos', {
            'fields': ('form_data', 'calculated_values', 'validation_errors'),
            'classes': ('collapse',)
        }),
        ('Montos', {
            'fields': ('total_tax_due', 'total_paid', 'balance_due')
        }),
        ('SII', {
            'fields': ('sii_folio', 'sii_response'),
            'classes': ('collapse',)
        }),
        ('Extracción de Detalles', {
            'fields': ('details_extracted', 'details_extracted_at', 'details_extraction_method', 'needs_detail_extraction', 'has_recent_details', 'details_data'),
            'classes': ('collapse',),
            'description': 'Estado de extracción de detalles completos del formulario F29 usando obtener_formulario_f29'
        })
    )

    def get_company_display(self, obj):
        """Mostrar company con fallback a legacy fields"""
        if obj.company:
            return f"{obj.company.business_name} ({obj.company.tax_id})"
        return f"Legacy: {obj.company_rut}-{obj.company_dv}"
    get_company_display.short_description = 'Company'
    get_company_display.admin_order_field = 'company__business_name'

    def get_details_status(self, obj):
        """Mostrar estado de extracción de detalles"""
        if not obj.sii_folio:
            return "Sin folio SII"

        if obj.details_extracted:
            if obj.has_recent_details:
                return "✅ Recientes"
            else:
                return f"✅ {obj.details_extracted_at.strftime('%d/%m/%y')}"
        else:
            return "❌ Pendiente"
    get_details_status.short_description = 'Detalles F29'
    get_details_status.admin_order_field = 'details_extracted'


class TaxFormFieldInline(admin.TabularInline):
    model = TaxFormField
    extra = 0
    readonly_fields = ('value',)


@admin.register(TaxFormField)
class TaxFormFieldAdmin(admin.ModelAdmin):
    list_display = ('form', 'field_code', 'field_name', 'field_type', 'is_required', 'is_calculated')
    list_filter = ('field_type', 'is_required', 'is_calculated')
    search_fields = ('field_code', 'field_name')
    readonly_fields = ('value',)


@admin.register(TaxFormPayment)
class TaxFormPaymentAdmin(admin.ModelAdmin):
    list_display = ('form', 'payment_method', 'amount', 'payment_date', 'status')
    list_filter = ('payment_method', 'status', 'payment_date')
    search_fields = ('transaction_id', 'authorization_code', 'receipt_number')


@admin.register(TaxFormAuditLog)
class TaxFormAuditLogAdmin(admin.ModelAdmin):
    list_display = ('form', 'user_email', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user_email', 'description')
    readonly_fields = ('created_at',)
