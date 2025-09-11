from .base import *

# Development settings
DEBUG = True

# Database for development (override if needed)
# Uses docker-compose database by default

# Add development apps
INSTALLED_APPS += [
    'django_extensions',
]

# Development middleware
MIDDLEWARE += [
    # Add any development-specific middleware here
]

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development-specific logging
LOGGING['handlers']['file'] = {
    'level': 'DEBUG',
    'class': 'logging.FileHandler',
    'filename': BASE_DIR / 'logs' / 'django.log',
    'formatter': 'verbose',
}

LOGGING['root']['handlers'].append('file')
LOGGING['loggers']['django']['handlers'].append('file')
LOGGING['loggers']['apps']['handlers'].append('file')

# Django Extensions
SHELL_PLUS_PRINT_SQL = True

# Celery settings for development
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# Create logs directory
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# CORS settings for development - more permissive
CORS_ALLOW_ALL_ORIGINS = True  # Permite TODOS los orígenes en desarrollo
CORS_ALLOW_CREDENTIALS = True   # Necesario para cookies/auth

# Si CORS_ALLOW_ALL_ORIGINS es True, esta lista se ignora, pero la dejamos por documentación
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://0.0.0.0:8080",  # Agregamos también 0.0.0.0
]

# Allow all headers for development
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Opcional: para debug
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']