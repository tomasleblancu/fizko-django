"""
Celery configuration for Fizko Django backend.
"""
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fizko_django.settings')

# Create Celery app
app = Celery('fizko_django')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Configure task routing by queue with priorities
app.conf.task_routes = {
    'apps.sii.tasks.*': {'queue': 'sii', 'routing_key': 'sii'},
    'apps.documents.tasks.*': {'queue': 'documents', 'routing_key': 'documents'},
    'apps.forms.tasks.*': {'queue': 'forms', 'routing_key': 'forms'},
    'apps.analytics.tasks.*': {'queue': 'analytics', 'routing_key': 'analytics'},
    'apps.ai_assistant.tasks.*': {'queue': 'ai', 'routing_key': 'ai'},
    'apps.notifications.tasks.*': {'queue': 'notifications', 'routing_key': 'notifications'},
}

# Queue configuration with priorities
app.conf.task_create_missing_queues = True
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange_type = 'direct'
app.conf.task_default_routing_key = 'default'

# Task execution configuration
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 4
app.conf.worker_max_tasks_per_child = 1000

# Task serialization
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']

# Task results
app.conf.result_expires = 3600  # 1 hour
app.conf.result_persistent = True

# Timezone configuration
app.conf.timezone = 'America/Santiago'
app.conf.enable_utc = True

# Celery Beat periodic tasks schedule
app.conf.beat_schedule = {
    # Sync SII data daily at 6 AM
    'sync-sii-daily': {
        'task': 'apps.sii.tasks.sync_all_companies_daily',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'sii'},
    },
    
    # Generate monthly reports on the 1st of each month
    'generate-monthly-reports': {
        'task': 'apps.analytics.tasks.generate_monthly_reports',
        'schedule': crontab(day_of_month=1, hour=0, minute=0),
        'options': {'queue': 'analytics'},
    },
    
    # Cleanup expired SII sessions daily at 2 AM
    'cleanup-sii-sessions': {
        'task': 'apps.sii.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'sii'},
    },
    
    # Process pending documents every 30 minutes
    'process-pending-documents': {
        'task': 'apps.documents.tasks.process_pending_documents',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'documents'},
    },
    
    # Update exchange rates daily at 9 AM
    'update-exchange-rates': {
        'task': 'apps.rates.tasks.update_exchange_rates',
        'schedule': crontab(hour=9, minute=0),
        'options': {'queue': 'default'},
    },
    
    # Send pending notifications every 5 minutes
    'send-pending-notifications': {
        'task': 'apps.notifications.tasks.send_pending_notifications',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'notifications'},
    },
    
    # Calculate F29 forms on the 15th of each month
    'calculate-monthly-f29': {
        'task': 'apps.forms.tasks.calculate_monthly_f29_for_all',
        'schedule': crontab(day_of_month=15, hour=10, minute=0),
        'options': {'queue': 'forms'},
    },
    
    # Cleanup old task results weekly
    'cleanup-task-results': {
        'task': 'apps.tasks.tasks.cleanup.cleanup_old_results',
        'schedule': crontab(day_of_week=1, hour=1, minute=0),  # Monday at 1 AM
        'options': {'queue': 'default'},
    },
}

# Beat scheduler
app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'

# Error handling
app.conf.task_reject_on_worker_lost = True
app.conf.task_ignore_result = False


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery configuration"""
    print(f'Request: {self.request!r}')
    return 'Debug task completed successfully'


# Signal handlers
@app.task(bind=True)
def test_celery_connection(self):
    """Test task to verify Celery is working"""
    return f'Celery is working! Task ID: {self.request.id}'


if __name__ == '__main__':
    app.start()