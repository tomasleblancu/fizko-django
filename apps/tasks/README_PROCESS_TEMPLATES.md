# Process Templates and Automatic Process Creation

This module provides automated process template seeding and ensures all companies have the required Chilean tax processes.

## Features

### 1. Process Template Seeding
- **F29 Monthly Tax Declaration**: Complete workflow for monthly IVA declarations
- **F22 Annual Tax Declaration**: Annual income tax declaration process
- **Document Synchronization**: Weekly automated SII document sync
- **IVA Purchase Books**: Monthly purchase book processing
- **IVA Sales Books**: Monthly sales book processing
- **F3323 Pro Pyme**: Quarterly simplified tax regime declarations

### 2. Automatic Process Creation
- Ensures all companies have required tax processes for current periods
- Supports both individual company and bulk company processing
- Includes dry-run mode for testing without creating actual processes
- Smart detection of existing processes to avoid duplicates

## Management Commands

### Seed Process Templates
```bash
# Basic seeding
python manage.py seed_process_templates

# Clear existing templates first
python manage.py seed_process_templates --clear

# Verbose output
python manage.py seed_process_templates --verbose --clear
```

### Test Process Creation
```bash
# Test all companies (dry run)
python manage.py test_process_creation --all-companies --dry-run

# Test specific company (dry run)
python manage.py test_process_creation --company-rut 12345678 --company-dv 9 --dry-run

# Actually create processes for specific company
python manage.py test_process_creation --company-rut 12345678 --company-dv 9

# Create processes for all companies
python manage.py test_process_creation --all-companies
```

## Celery Tasks

### Individual Company Process Assurance
```python
from apps.tasks.tasks import ensure_company_processes

# Ensure a company has all required processes
result = ensure_company_processes('12345678', '9')
print(f"Created {result['created_count']} processes")
```

### Bulk Company Process Assurance
```python
from apps.tasks.tasks import ensure_all_companies_have_processes

# Dry run to see what would be created
result = ensure_all_companies_have_processes(dry_run=True)
print(f"Would create {result['total_processes_created']} processes")

# Actually create missing processes
result = ensure_all_companies_have_processes(dry_run=False)
print(f"Created {result['total_processes_created']} processes")
```

## Process Templates Created

### F29 - Monthly IVA Declaration
- **Frequency**: Monthly (due 12th of following month)
- **Tasks**: 8 tasks from document sync to payment management
- **Automation**: Full automation with manual approval checkpoints
- **Recurrence**: Automatically generates next month's process

### F22 - Annual Income Tax Declaration
- **Frequency**: Annual (due April 30th)
- **Tasks**: 10 tasks including balance preparation and external review
- **Complexity**: High - requires accounting expertise
- **Duration**: Typically 60 days preparation time

### Document Synchronization
- **Frequency**: Weekly (Mondays)
- **Tasks**: 5 automated tasks for SII integration
- **Purpose**: Keep documents updated with SII portal
- **Duration**: Approximately 2 hours

### IVA Books (Purchase & Sales)
- **Frequency**: Monthly
- **Tasks**: 5 tasks each for purchase and sales book processing
- **Integration**: Direct SII portal integration
- **Purpose**: VAT credit/debit calculation

### F3323 - Pro Pyme Quarterly Declaration
- **Frequency**: Quarterly (due 20th of following month)
- **Tasks**: 7 tasks for simplified regime compliance
- **Eligibility**: Only for companies in Pro Pyme regime
- **Automation**: Validates regime requirements automatically

## Task Categories

The system creates 6 task categories:

1. **Tributario** (Tax) - Green (#4CAF50)
2. **Documentos** (Documents) - Blue (#2196F3)
3. **Sincronización** (Sync) - Orange (#FF9800)
4. **Revisión** (Review) - Purple (#9C27B0)
5. **Pagos** (Payments) - Red (#F44336)
6. **Análisis** (Analysis) - Cyan (#00BCD4)

## Process Logic

### Smart Process Creation
- **Current Month F29**: Always ensures current month process exists
- **Next Month F29**: Creates if after 5th of current month (early preparation)
- **Annual F22**: Only between January-April for previous year
- **Pro Pyme F3323**: Only for companies with `tax_regime = 'pro_pyme'`

### Edge Case Handling
- Prevents duplicate process creation
- Handles company model availability gracefully
- Supports both database-driven and process-derived company lists
- Robust error handling with detailed logging

### Due Date Calculations
- **F29**: 12th of month following the tax period
- **F22**: April 30th for previous year
- **F3323**: 20th of month following the quarter
- **Task deadlines**: Calculated relative to process due dates

## Integration with Existing Systems

### Company Model Integration
- Automatically detects company email for process assignment
- Supports `tax_id` format (RUT-DV) used in company model
- Falls back to process-derived company data if Company model unavailable

### SII Integration Ready
- All templates include SII credential requirements
- Tasks configured for automatic SII portal interaction
- Document sync processes maintain SII compliance

### Notification Integration
- Automatic notifications when processes are created
- WhatsApp integration ready (if available)
- Email notifications for process assignments

## Monitoring and Maintenance

### Logging
- Comprehensive logging at INFO level for successful operations
- ERROR level for failures with full context
- Celery task retry logic for transient failures

### Health Checks
- Dry-run capabilities for testing
- Process existence verification before creation
- Template availability validation

### Performance Considerations
- Bulk operations use database transactions
- Efficient queries to prevent N+1 problems
- Background task processing for large company sets

## Usage in Production

### Scheduled Tasks
```python
# Add to Celery Beat schedule
CELERY_BEAT_SCHEDULE = {
    'ensure-monthly-processes': {
        'task': 'apps.tasks.tasks.ensure_all_companies_have_processes',
        'schedule': crontab(day_of_month=1, hour=2),  # 1st of month at 2 AM
    },
}
```

### Manual Execution
```bash
# For new company onboarding
docker-compose exec django python manage.py shell -c "
from apps.tasks.tasks import ensure_company_processes
ensure_company_processes('NEW_RUT', 'DV', 'owner@company.com')
"
```

### Error Recovery
```bash
# Re-run with force create if needed
docker-compose exec django python manage.py shell -c "
from apps.tasks.tasks import ensure_company_processes
ensure_company_processes('RUT', 'DV', force_create=True)
"
```

## Troubleshooting

### Common Issues

1. **"No templates found"**: Run `seed_process_templates` first
2. **Company not found**: Verify company exists and is active
3. **Permission errors**: Check user assignment and permissions
4. **Date calculation errors**: Verify timezone settings

### Debug Mode
```python
# Enable detailed logging
import logging
logging.getLogger('apps.tasks.tasks').setLevel(logging.DEBUG)
```

This system provides a robust foundation for automated Chilean tax process management with full auditability and error handling.