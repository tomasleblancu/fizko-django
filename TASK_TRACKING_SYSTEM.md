# Background Task Tracking System

This document describes the implementation of the background task tracking system for Fizko, designed to monitor and display the progress of long-running tasks during company onboarding.

## Overview

The system tracks background tasks (primarily Celery tasks) associated with companies and provides a real-time API endpoint for frontend consumption. It's especially useful during the onboarding process where users need to see the progress of data synchronization tasks.

## Components

### 1. Database Model (`BackgroundTaskTracker`)

**Location**: `apps/companies/models.py`

The `BackgroundTaskTracker` model stores metadata about background tasks:

```python
class BackgroundTaskTracker(TimeStampedModel):
    company = models.ForeignKey(Company)  # Associated company
    task_id = models.CharField()          # Celery task ID
    task_name = models.CharField()        # Internal task identifier
    display_name = models.CharField()     # User-friendly name
    status = models.CharField()           # pending|running|success|failed
    progress = models.IntegerField()      # 0-100 progress percentage
    started_at = models.DateTimeField()   # When task began execution
    completed_at = models.DateTimeField() # When task finished
    error_message = models.TextField()    # Error details if failed
    metadata = models.JSONField()         # Additional task information
```

**Key Features**:
- Automatic cleanup of old completed tasks
- Integration with Celery result backend
- Company-specific task isolation
- Progress tracking support

### 2. API Endpoint

**URL**: `GET /api/v1/companies/{company_id}/task_status/`

**Authentication**: Required (user must have access to the company)

**Response Format**:
```json
{
  "active_tasks": [
    {
      "task_id": "abc123-def456",
      "name": "Creando procesos tributarios",
      "status": "running",
      "progress": 50,
      "started_at": "2024-01-01T10:00:00Z",
      "task_type": "create_processes_from_taxpayer_settings",
      "duration_seconds": 30.5
    }
  ],
  "all_completed": false,
  "summary": {
    "total_tasks": 4,
    "active_count": 1,
    "completed_count": 3,
    "recent_completed": [...]
  },
  "company_id": 73,
  "company_name": "Example Company",
  "checked_at": "2024-01-01T10:05:00Z"
}
```

**Key Features**:
- Real-time status updates from Celery
- Automatic task state synchronization
- Company access control via existing permissions
- Detailed progress information

### 3. Onboarding Integration

**Location**: `apps/onboarding/views.py`

The system is integrated into the onboarding finalize process to track these specific tasks:

1. **`create_processes_from_taxpayer_settings`**: Creates tax processes for the company
2. **`sync_sii_documents_task`**: Initial document synchronization (last 2 months)
3. **`sync_sii_documents_full_history_task`**: Complete historical document sync
4. **`sync_all_historical_forms_task`**: Historical tax forms synchronization

**Integration Example**:
```python
# In onboarding finalize method
task_result = sync_sii_documents_task.delay(...)

# Create tracker
BackgroundTaskTracker.create_for_task(
    company=company,
    task_result=task_result,
    task_name='sync_sii_documents_task',
    display_name='Sincronizando documentos SII',
    metadata={'sync_type': 'initial', 'company_id': company_id}
)
```

### 4. Cleanup Tasks

**Location**: `apps/companies/tasks.py`

Three Celery tasks handle system maintenance:

#### `cleanup_old_completed_tasks`
- **Schedule**: Every hour
- **Purpose**: Removes completed tasks older than 1 hour
- **Queue**: `default`

#### `update_task_statuses`
- **Schedule**: Every 2 minutes
- **Purpose**: Synchronizes task states with Celery backend
- **Queue**: `default`

#### `cleanup_orphaned_trackers`
- **Schedule**: Every 24 hours
- **Purpose**: Cleans up trackers for tasks that no longer exist in Celery
- **Queue**: `default`

### 5. Periodic Task Configuration

**Location**: `fizko_django/settings.py`

Automatic task scheduling via Celery Beat:

```python
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-completed-tasks': {
        'task': 'companies.cleanup_old_completed_tasks',
        'schedule': 3600.0,  # Every hour
        'args': (1,),        # Clean tasks older than 1 hour
    },
    'update-task-statuses': {
        'task': 'companies.update_task_statuses',
        'schedule': 120.0,   # Every 2 minutes
    },
    'cleanup-orphaned-trackers': {
        'task': 'companies.cleanup_orphaned_trackers',
        'schedule': 86400.0, # Every 24 hours
        'args': (24,),       # Clean trackers older than 24 hours
    },
}
```

## Usage

### For Frontend Developers

1. **Poll the API endpoint** every 5-10 seconds during onboarding:
   ```javascript
   const response = await fetch(`/api/v1/companies/${companyId}/task_status/`);
   const data = await response.json();
   ```

2. **Display progress** based on the response:
   ```javascript
   data.active_tasks.forEach(task => {
     console.log(`${task.name}: ${task.progress}% (${task.status})`);
   });

   if (data.all_completed) {
     // All background tasks finished - onboarding complete
   }
   ```

3. **Handle different task states**:
   - `pending`: Task queued but not started
   - `running`: Task actively executing
   - `success`: Task completed successfully
   - `failed`: Task failed with error

### For Backend Developers

1. **Create task trackers** when launching background tasks:
   ```python
   from apps.companies.models import BackgroundTaskTracker

   # Launch Celery task
   task_result = my_background_task.delay(param1, param2)

   # Create tracker
   BackgroundTaskTracker.create_for_task(
       company=company,
       task_result=task_result,
       task_name='my_background_task',
       display_name='Processing user data',
       metadata={'param1': param1, 'param2': param2}
   )
   ```

2. **Update progress from within tasks** (optional):
   ```python
   from celery import current_task

   @shared_task(bind=True)
   def my_background_task(self, param1, param2):
       # Update progress
       self.update_state(
           state='PROGRESS',
           meta={'progress': 25, 'status': 'Processing step 1'}
       )
   ```

## Database Migration

The system includes a migration that creates the `background_task_trackers` table:

```bash
docker-compose exec django python manage.py migrate companies
```

## Security Considerations

- **Company Access Control**: Users can only see tasks for companies they have access to
- **Task Isolation**: Tasks are isolated by company to prevent data leakage
- **Automatic Cleanup**: Old tasks are automatically removed to prevent database bloat
- **Error Handling**: Failed task retrieval doesn't crash the API endpoint

## Performance Considerations

- **Efficient Queries**: Uses database indexes on company, status, and task_id
- **Automatic Cleanup**: Prevents unlimited database growth
- **Celery Integration**: Direct integration with Celery result backend for real-time status
- **Pagination**: API returns only active tasks by default to minimize payload size

## Monitoring

- **Celery Flower**: Monitor task execution at http://localhost:5555
- **Django Admin**: View and manage task trackers via admin interface
- **API Logs**: Task status requests are logged for debugging
- **Cleanup Metrics**: Cleanup tasks report statistics for monitoring

## Future Enhancements

- **WebSocket Support**: Real-time updates without polling
- **Progress Webhooks**: Notify external systems when tasks complete
- **Task Dependencies**: Track relationships between dependent tasks
- **Advanced Filtering**: Filter tasks by type, date range, or status
- **Task Retry Logic**: Automatic retry of failed tasks with exponential backoff

## Testing

The system includes comprehensive testing functionality:

```python
# Test API endpoint
from rest_framework.test import APIClient
client = APIClient()
client.force_authenticate(user=user)
response = client.get(f'/api/v1/companies/{company_id}/task_status/')
```

## Conclusion

This background task tracking system provides a robust foundation for monitoring long-running operations in Fizko. It enhances user experience during onboarding by providing real-time feedback and maintains system health through automatic cleanup processes.

The system is designed to be:
- **Scalable**: Handles multiple companies and concurrent tasks
- **Reliable**: Automatic error handling and recovery
- **User-friendly**: Clear progress indication and status messages
- **Maintainable**: Clean separation of concerns and comprehensive documentation