from django.db import models
from apps.core.models import TimeStampedModel

class ExpenseCategory(TimeStampedModel):
    """
    Categorías de gastos
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=20, unique=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'expense_categories'
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Expense(TimeStampedModel):
    """
    Gastos de la empresa
    """
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('paid', 'Pagado'),
    ]
    
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)
    
    # Información básica
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    
    # Proveedor
    supplier_rut = models.CharField(max_length=12, blank=True)
    supplier_dv = models.CharField(max_length=1, blank=True)
    supplier_name = models.CharField(max_length=255)
    
    # Montos
    net_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Fechas
    expense_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    
    # Estado y aprobación
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.EmailField()
    approved_by = models.EmailField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Documentos
    invoice_number = models.CharField(max_length=50, blank=True)
    receipt_file = models.FileField(upload_to='expenses/receipts/', blank=True, null=True)
    
    class Meta:
        db_table = 'expenses'
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering = ['-expense_date']
        indexes = [
            models.Index(fields=['company_rut', 'company_dv']),
            models.Index(fields=['expense_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} - ${self.total_amount}"
