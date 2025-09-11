import dj_database_url
from .base import *

# Railway production settings
DEBUG = False

# Railway provides RAILWAY_STATIC_URL and RAILWAY_PUBLIC_DOMAIN
ALLOWED_HOSTS = ['*']  # Railway handles domain routing

# CORS Configuration for Vercel frontend
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)

# If CORS_ALLOWED_ORIGINS is empty, set defaults for Vercel
if not CORS_ALLOWED_ORIGINS:
    # For production, you should set specific domains via env variable
    # Example: CORS_ALLOWED_ORIGINS=https://fizko.vercel.app,https://your-domain.com
    pass

# Allow regex patterns for Vercel preview deployments
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",  # All Vercel preview deployments
]

CORS_ALLOW_CREDENTIALS = True

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Only enable HTTPS redirect if not behind Railway's proxy
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)

# Production apps
INSTALLED_APPS += [
    'django_health_check',
    'health_check.db',
    'health_check.cache',
]

# Static files with whitenoise
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Database - Railway provides DATABASE_URL automatically
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Redis - Railway provides REDIS_URL automatically  
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Celery configuration for Railway
CELERY_BROKER_URL = config('REDIS_URL')
CELERY_RESULT_BACKEND = config('REDIS_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery routing for Railway services
CELERY_TASK_ROUTES = {
    'apps.sii.tasks.*': {'queue': 'sii'},
    'apps.documents.tasks.*': {'queue': 'documents'},
    'apps.whatsapp.tasks.*': {'queue': 'whatsapp'},
    'apps.forms.tasks.*': {'queue': 'default'},
    'apps.analytics.tasks.*': {'queue': 'default'},
    'apps.notifications.tasks.*': {'queue': 'default'},
}

# Production logging optimized for Railway
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Email configuration for production (if needed)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Performance optimizations
CONN_MAX_AGE = 300

# Session configuration
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)

# Sentry configuration for error tracking (optional)
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='railway-production'
    )