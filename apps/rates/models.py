from django.db import models
from apps.core.models import TimeStampedModel

class ExchangeRate(TimeStampedModel):
    """
    Tipos de cambio de monedas
    """
    CURRENCY_CHOICES = [
        ('USD', 'Dólar Estadounidense'),
        ('EUR', 'Euro'),
        ('UF', 'Unidad de Fomento'),
        ('UTM', 'Unidad Tributaria Mensual'),
        ('UTA', 'Unidad Tributaria Anual'),
    ]
    
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    date = models.DateField()
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    source = models.CharField(max_length=50, default='SII', help_text="Fuente del tipo de cambio")
    
    class Meta:
        db_table = 'exchange_rates'
        verbose_name = 'Exchange Rate'
        verbose_name_plural = 'Exchange Rates'
        unique_together = ['currency', 'date']
        ordering = ['-date', 'currency']
    
    def __str__(self):
        return f"{self.get_currency_display()} - {self.rate} ({self.date})"


class TaxRate(TimeStampedModel):
    """
    Tasas tributarias (IVA, impuestos específicos, etc.)
    """
    TAX_TYPES = [
        ('iva', 'IVA'),
        ('specific', 'Impuesto Específico'),
        ('additional', 'Impuesto Adicional'),
        ('retention', 'Retención'),
    ]
    
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES)
    name = models.CharField(max_length=100)
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'tax_rates'
        verbose_name = 'Tax Rate'
        verbose_name_plural = 'Tax Rates'
        ordering = ['-effective_from', 'tax_type']
    
    def __str__(self):
        return f"{self.name} - {self.rate}%"
    
    @property
    def is_current(self):
        """Verifica si la tasa está vigente"""
        from datetime import date
        today = date.today()
        if self.effective_until:
            return self.effective_from <= today <= self.effective_until
        return self.effective_from <= today
