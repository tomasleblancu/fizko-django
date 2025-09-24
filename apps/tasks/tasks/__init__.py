"""
Tasks package - Modular Celery task organization

This package imports all task modules to ensure Celery autodiscovery works properly.
Each module contains logically grouped tasks:

- process_management: Process creation, updates, and lifecycle management
- deadlines: Deadline checking and alert tasks
- notifications: Notification sending tasks
- cleanup: Cleanup and maintenance tasks
- recurring: Recurring process generation tasks
"""

# Import all tasks to make them discoverable by Celery
from .process_management import *
from .deadlines import *
from .notifications import *
from .cleanup import *
from .recurring import *