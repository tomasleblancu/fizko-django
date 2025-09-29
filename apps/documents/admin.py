from django.contrib import admin
from .models import DocumentType, Document


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'is_electronic', 'requires_recipient', 'is_active')
    list_filter = ('category', 'is_electronic', 'requires_recipient', 'is_active')
    search_fields = ('code', 'name', 'description')
    ordering = ('code',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('document_type', 'folio', 'issue_date', 'recipient_name', 'total_amount', 'status', 'company')
    list_filter = ('document_type', 'status', 'issue_date', 'company')
    search_fields = ('folio', 'recipient_name', 'recipient_rut', 'issuer_name')
    readonly_fields = ('issuer_full_rut', 'recipient_full_rut', 'document_direction')
    
    fieldsets = (
        ('Empresa', {
            'fields': ('company', 'document_direction')
        }),
        ('Emisor', {
            'fields': ('issuer_company_rut', 'issuer_company_dv', 'issuer_full_rut', 'issuer_name', 'issuer_address', 'issuer_activity')
        }),
        ('Documento', {
            'fields': ('document_type', 'folio', 'issue_date', 'status')
        }),
        ('Receptor', {
            'fields': ('recipient_rut', 'recipient_dv', 'recipient_full_rut', 'recipient_name', 'recipient_address')
        }),
        ('Montos', {
            'fields': ('net_amount', 'tax_amount', 'exempt_amount', 'total_amount')
        }),
        ('SII', {
            'fields': ('sii_track_id', 'sii_response', 'xml_data', 'pdf_file')
        }),
        ('Referencias', {
            'fields': ('reference_document', 'reference_reason', 'reference_folio', 'reference_folio_type')
        })
    )
