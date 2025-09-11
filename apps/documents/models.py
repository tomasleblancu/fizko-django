from django.db import models
from apps.core.models import TimeStampedModel

class DocumentType(TimeStampedModel):
    """
    Tipos de documentos tributarios chilenos (DTEs y otros)
    """
    # Códigos DTE del SII más comunes
    DTE_CODES = [
        (33, 'Factura Electrónica'),
        (34, 'Factura No Afecta o Exenta Electrónica'),
        (39, 'Boleta Electrónica'),
        (41, 'Boleta No Afecta o Exenta Electrónica'),
        (46, 'Factura de Compra Electrónica'),
        (52, 'Guía de Despacho Electrónica'),
        (56, 'Nota de Débito Electrónica'),
        (61, 'Nota de Crédito Electrónica'),
        (110, 'Factura de Exportación Electrónica'),
        (111, 'Nota de Débito de Exportación Electrónica'),
        (112, 'Nota de Crédito de Exportación Electrónica'),
    ]
    
    code = models.IntegerField(unique=True, help_text="Código SII del documento")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=[
        ('invoice', 'Facturas'),
        ('receipt', 'Boletas'),
        ('credit_note', 'Notas de Crédito'),
        ('debit_note', 'Notas de Débito'),
        ('dispatch', 'Guías de Despacho'),
        ('export', 'Exportación'),
        ('other', 'Otros'),
    ])
    is_electronic = models.BooleanField(default=True)
    is_dte = models.BooleanField(default=False, help_text="Es un DTE (Documento Tributario Electrónico)")
    requires_recipient = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'document_types'
        verbose_name = 'Document Type'
        verbose_name_plural = 'Document Types'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Document(TimeStampedModel):
    """
    Documento tributario base
    """
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('signed', 'Firmado'),
        ('sent', 'Enviado al SII'),
        ('accepted', 'Aceptado por SII'),
        ('rejected', 'Rechazado por SII'),
        ('cancelled', 'Anulado'),
        ('processed', 'Procesado'),
    ]
    
    # Relación con Company (empresa propietaria del documento)
    company = models.ForeignKey(
        'companies.Company', 
        on_delete=models.PROTECT,
        related_name='documents',
        null=True,  # Temporalmente nullable para migración
        blank=True,
        help_text="Empresa propietaria del documento (emisor para docs emitidos, receptor para docs recibidos)"
    )
    
    # Emisor
    issuer_company_rut = models.CharField(max_length=12)
    issuer_company_dv = models.CharField(max_length=1)
    issuer_name = models.CharField(max_length=255)
    issuer_address = models.CharField(max_length=500)
    issuer_activity = models.CharField(max_length=255, blank=True)
    
    # Receptor
    recipient_rut = models.CharField(max_length=12)
    recipient_dv = models.CharField(max_length=1)
    recipient_name = models.CharField(max_length=255)
    recipient_address = models.CharField(max_length=500, blank=True)
    
    # Documento
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT)
    folio = models.IntegerField()
    issue_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Montos
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    exempt_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # SII
    sii_track_id = models.CharField(max_length=50, blank=True)
    sii_response = models.JSONField(default=dict)
    xml_data = models.TextField(blank=True)
    pdf_file = models.FileField(upload_to='documents/pdfs/', blank=True, null=True)
    raw_data = models.JSONField(default=dict, blank=True, help_text="Datos originales del SII sin procesar")
    
    # Referencias (notas de crédito/débito)
    reference_document = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='references')
    reference_reason = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'documents'
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        unique_together = ['issuer_company_rut', 'issuer_company_dv', 'document_type', 'folio']
        ordering = ['-issue_date', '-folio']
        indexes = [
            models.Index(fields=['issuer_company_rut', 'issuer_company_dv']),
            models.Index(fields=['recipient_rut', 'recipient_dv']),
            models.Index(fields=['document_type', 'folio']),
            models.Index(fields=['issue_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.document_type.name} {self.folio} - {self.recipient_name}"
    
    @property
    def issuer_full_rut(self):
        return f"{self.issuer_company_rut}-{self.issuer_company_dv}"
    
    @property
    def recipient_full_rut(self):
        return f"{self.recipient_rut}-{self.recipient_dv}"
    
    @property
    def is_issued_by_company(self):
        """True if this document was issued by the related company"""
        return (self.issuer_company_rut == self.company.tax_id.split('-')[0] and 
                self.issuer_company_dv.upper() == self.company.tax_id.split('-')[1].upper())
    
    @property
    def is_received_by_company(self):
        """True if this document was received by the related company"""
        return (self.recipient_rut == self.company.tax_id.split('-')[0] and 
                self.recipient_dv.upper() == self.company.tax_id.split('-')[1].upper())
    
    @property
    def document_direction(self):
        """Returns 'issued' or 'received' based on company relationship"""
        if self.is_issued_by_company:
            return 'issued'
        elif self.is_received_by_company:
            return 'received'
        else:
            return 'unknown'
    
    @classmethod
    def get_company_for_document(cls, issuer_rut, issuer_dv, recipient_rut, recipient_dv):
        """
        Determines which company should own this document based on RUTs.
        Prioritizes company as issuer, then as recipient.
        """
        from apps.companies.models import Company
        
        # First try to find company as issuer
        issuer_tax_id = f"{issuer_rut}-{issuer_dv}".upper()
        try:
            return Company.objects.get(tax_id=issuer_tax_id)
        except Company.DoesNotExist:
            pass
        
        # Then try as recipient
        recipient_tax_id = f"{recipient_rut}-{recipient_dv}".upper()
        try:
            return Company.objects.get(tax_id=recipient_tax_id)
        except Company.DoesNotExist:
            pass
        
        return None


