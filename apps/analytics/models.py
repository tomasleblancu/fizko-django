from django.db import models
from apps.core.models import TimeStampedModel

class AnalyticsReport(TimeStampedModel):
    """
    Reportes analíticos
    """
    REPORT_TYPES = [
        ('tax_summary', 'Resumen Tributario'),
        ('expense_analysis', 'Análisis de Gastos'),
        ('revenue_analysis', 'Análisis de Ingresos'),
        ('cash_flow', 'Flujo de Caja'),
        ('profitability', 'Rentabilidad'),
        ('tax_compliance', 'Cumplimiento Tributario'),
    ]
    
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    title = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Datos del reporte
    report_data = models.JSONField(default=dict)
    generated_by = models.EmailField()
    file_path = models.CharField(max_length=500, blank=True)
    
    class Meta:
        db_table = 'analytics_reports'
        verbose_name = 'Analytics Report'
        verbose_name_plural = 'Analytics Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.period_start} - {self.period_end})"


class Metric(TimeStampedModel):
    """
    Métricas del sistema
    """
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)
    metric_name = models.CharField(max_length=100)
    metric_value = models.DecimalField(max_digits=20, decimal_places=6)
    metric_date = models.DateField()
    
    class Meta:
        db_table = 'metrics'
        verbose_name = 'Metric'
        verbose_name_plural = 'Metrics'
        unique_together = ['company_rut', 'company_dv', 'metric_name', 'metric_date']
    
    def __str__(self):
        return f"{self.metric_name}: {self.metric_value}"
