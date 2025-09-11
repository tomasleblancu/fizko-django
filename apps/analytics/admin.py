from django.contrib import admin
from .models import AnalyticsReport, Metric

@admin.register(AnalyticsReport)
class AnalyticsReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_rut', 'report_type', 'period_start', 'period_end', 'generated_by')
    list_filter = ('report_type', 'created_at')
    search_fields = ('title', 'company_rut', 'generated_by')

@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ('company_rut', 'metric_name', 'metric_value', 'metric_date')
    list_filter = ('metric_name', 'metric_date')
    search_fields = ('company_rut', 'metric_name')
