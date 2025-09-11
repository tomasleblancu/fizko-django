from django.contrib import admin
from .models import ExpenseCategory, Expense

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'parent', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'code', 'description')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'company_rut', 'supplier_name', 'total_amount', 'expense_date', 'status')
    list_filter = ('status', 'category', 'expense_date')
    search_fields = ('title', 'supplier_name', 'invoice_number')
