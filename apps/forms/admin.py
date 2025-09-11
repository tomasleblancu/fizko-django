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
    list_display = ('company_rut', 'company_dv', 'template', 'tax_period', 'status', 'total_tax_due', 'is_overdue')
    list_filter = ('template', 'status', 'tax_year', 'due_date')
    search_fields = ('company_rut', 'sii_folio')
    readonly_fields = ('is_overdue', 'balance_due')
    
    fieldsets = (
        ('Empresa', {
            'fields': ('company_rut', 'company_dv', 'template')
        }),
        ('Período', {
            'fields': ('tax_year', 'tax_month', 'tax_period')
        }),
        ('Estado', {
            'fields': ('status', 'due_date', 'submission_date', 'is_overdue')
        }),
        ('Datos', {
            'fields': ('form_data', 'calculated_values', 'validation_errors')
        }),
        ('Montos', {
            'fields': ('total_tax_due', 'total_paid', 'balance_due')
        }),
        ('SII', {
            'fields': ('sii_folio', 'sii_response')
        })
    )


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
