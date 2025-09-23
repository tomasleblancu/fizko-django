"""
Tareas de Celery para sincronización SII
"""

from .documents import sync_sii_documents_task, sync_sii_documents_full_history_task
from .company import sync_company_data_task
from .forms import (
    sync_tax_forms_task,
    sync_all_historical_forms_task,
    extract_form_details_task,
    extract_multiple_forms_details_task
)

__all__ = [
    'sync_sii_documents_task',
    'sync_sii_documents_full_history_task',
    'sync_company_data_task',
    'sync_tax_forms_task',
    'sync_all_historical_forms_task',
    'extract_form_details_task',
    'extract_multiple_forms_details_task',
]