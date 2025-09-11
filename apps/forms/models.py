from django.db import models
from apps.core.models import TimeStampedModel

class TaxFormTemplate(TimeStampedModel):
    """
    Plantillas de formularios tributarios
    """
    FORM_TYPES = [
        ('f29', 'Formulario 29 - Declaración Mensual IVA'),
        ('f3323', 'Formulario 3323 - Pago Provisional Mensual Renta'),
        ('f50', 'Formulario 50 - Declaración Anual Renta'),
        ('f1924', 'Formulario 1924 - Solicitud de Devolución'),
        ('f1923', 'Formulario 1923 - Declaración Jurada'),
        ('f22', 'Formulario 22 - Declaración Anual Renta'),
    ]
    
    form_code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    form_type = models.CharField(max_length=10, choices=FORM_TYPES)
    version = models.CharField(max_length=10, default='1.0')
    is_active = models.BooleanField(default=True)
    
    # Estructura del formulario
    form_structure = models.JSONField(default=dict, help_text="Estructura de campos del formulario")
    validation_rules = models.JSONField(default=dict, help_text="Reglas de validación")
    calculation_rules = models.JSONField(default=dict, help_text="Reglas de cálculo automático")
    
    class Meta:
        db_table = 'tax_form_templates'
        verbose_name = 'Tax Form Template'
        verbose_name_plural = 'Tax Form Templates'
        ordering = ['form_code']
    
    def __str__(self):
        return f"{self.form_code} - {self.name}"


class TaxForm(TimeStampedModel):
    """
    Instancia de formulario tributario completado
    """
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completado'),
        ('validated', 'Validado'),
        ('submitted', 'Enviado'),
        ('accepted', 'Aceptado'),
        ('rejected', 'Rechazado'),
        ('paid', 'Pagado'),
    ]
    
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)
    template = models.ForeignKey(TaxFormTemplate, on_delete=models.PROTECT)
    
    # Período tributario
    tax_year = models.IntegerField()
    tax_month = models.IntegerField(null=True, blank=True, help_text="Para formularios mensuales")
    tax_period = models.CharField(max_length=20, help_text="Período en formato YYYY-MM o YYYY")
    
    # Estado y fechas
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    due_date = models.DateField(null=True, blank=True)
    submission_date = models.DateTimeField(null=True, blank=True)
    
    # Datos del formulario
    form_data = models.JSONField(default=dict, help_text="Datos completados del formulario")
    calculated_values = models.JSONField(default=dict, help_text="Valores calculados automáticamente")
    validation_errors = models.JSONField(default=list, help_text="Errores de validación")
    
    # Montos principales
    total_tax_due = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # SII
    sii_folio = models.CharField(max_length=50, blank=True)
    sii_response = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'tax_forms'
        verbose_name = 'Tax Form'
        verbose_name_plural = 'Tax Forms'
        unique_together = ['company_rut', 'company_dv', 'template', 'tax_period']
        ordering = ['-tax_year', '-tax_month', 'template__form_code']
        indexes = [
            models.Index(fields=['company_rut', 'company_dv']),
            models.Index(fields=['template', 'tax_period']),
            models.Index(fields=['status', 'due_date']),
        ]
    
    def __str__(self):
        return f"{self.company_rut}-{self.company_dv} - {self.template.form_code} {self.tax_period}"
    
    @property
    def is_overdue(self):
        """Verifica si el formulario está vencido"""
        if self.status in ['submitted', 'accepted', 'paid'] or not self.due_date:
            return False
        from datetime import date
        return date.today() > self.due_date
    
    def calculate_balance(self):
        """Calcula el saldo pendiente"""
        if self.total_tax_due is not None:
            self.balance_due = self.total_tax_due - self.total_paid
            return self.balance_due
        return 0


class TaxFormField(TimeStampedModel):
    """
    Campos individuales de un formulario tributario
    """
    FIELD_TYPES = [
        ('text', 'Texto'),
        ('number', 'Número'),
        ('decimal', 'Decimal'),
        ('date', 'Fecha'),
        ('boolean', 'Booleano'),
        ('select', 'Selección'),
        ('calculation', 'Cálculo'),
    ]
    
    form = models.ForeignKey(TaxForm, on_delete=models.CASCADE, related_name='fields')
    field_code = models.CharField(max_length=20)
    field_name = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    section = models.CharField(max_length=50, blank=True, help_text="Sección del formulario")
    line_number = models.IntegerField(null=True, blank=True)
    
    # Valor del campo
    text_value = models.TextField(blank=True)
    number_value = models.BigIntegerField(null=True, blank=True)
    decimal_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    boolean_value = models.BooleanField(null=True, blank=True)
    
    # Metadatos
    is_required = models.BooleanField(default=False)
    is_calculated = models.BooleanField(default=False)
    calculation_formula = models.TextField(blank=True, help_text="Fórmula de cálculo")
    validation_rules = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'tax_form_fields'
        verbose_name = 'Tax Form Field'
        verbose_name_plural = 'Tax Form Fields'
        unique_together = ['form', 'field_code']
        ordering = ['section', 'line_number', 'field_code']
    
    def __str__(self):
        return f"{self.form} - {self.field_name} ({self.field_code})"
    
    @property
    def value(self):
        """Retorna el valor del campo según su tipo"""
        if self.field_type == 'text':
            return self.text_value
        elif self.field_type == 'number':
            return self.number_value
        elif self.field_type == 'decimal':
            return self.decimal_value
        elif self.field_type == 'date':
            return self.date_value
        elif self.field_type == 'boolean':
            return self.boolean_value
        return None


class TaxFormPayment(TimeStampedModel):
    """
    Pagos realizados para formularios tributarios
    """
    PAYMENT_METHODS = [
        ('online', 'Pago en Línea'),
        ('bank', 'Banco'),
        ('check', 'Cheque'),
        ('cash', 'Efectivo'),
        ('offset', 'Compensación'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado'),
    ]
    
    form = models.ForeignKey(TaxForm, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Detalles del pago
    bank_code = models.CharField(max_length=10, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    authorization_code = models.CharField(max_length=50, blank=True)
    receipt_number = models.CharField(max_length=50, blank=True)
    
    # SII
    sii_payment_id = models.CharField(max_length=50, blank=True)
    sii_response = models.JSONField(default=dict)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'tax_form_payments'
        verbose_name = 'Tax Form Payment'
        verbose_name_plural = 'Tax Form Payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.form} - Pago ${self.amount} ({self.get_payment_method_display()})"


class TaxFormAuditLog(TimeStampedModel):
    """
    Log de auditoría para cambios en formularios tributarios
    """
    ACTION_TYPES = [
        ('created', 'Creado'),
        ('updated', 'Actualizado'),
        ('validated', 'Validado'),
        ('submitted', 'Enviado'),
        ('payment_added', 'Pago Agregado'),
        ('status_changed', 'Estado Cambiado'),
        ('deleted', 'Eliminado'),
    ]
    
    form = models.ForeignKey(TaxForm, on_delete=models.CASCADE, related_name='audit_logs')
    user_email = models.EmailField()
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField(blank=True)
    
    # Datos del cambio
    old_values = models.JSONField(default=dict, help_text="Valores anteriores")
    new_values = models.JSONField(default=dict, help_text="Valores nuevos")
    
    # Metadatos
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'tax_form_audit_logs'
        verbose_name = 'Tax Form Audit Log'
        verbose_name_plural = 'Tax Form Audit Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.form} - {self.get_action_display()} por {self.user_email}"
