from django.contrib import admin
from .models import ExchangeRate, TaxRate

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('currency', 'date', 'rate', 'source')
    list_filter = ('currency', 'source', 'date')
    search_fields = ('currency',)

@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_type', 'rate', 'effective_from', 'effective_until', 'is_current', 'is_active')
    list_filter = ('tax_type', 'is_active', 'effective_from')
    search_fields = ('name', 'description')
    readonly_fields = ('is_current',)
