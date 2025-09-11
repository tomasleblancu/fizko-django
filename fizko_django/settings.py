"""
Django settings for fizko_django project.
Consolidated settings file with environment-based configuration.
"""

import os
import dj_database_url
from pathlib import Path
from decouple import config
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment detection
RAILWAY_ENVIRONMENT = config('RAILWAY_ENVIRONMENT', default='', cast=str)
IS_RAILWAY = bool(RAILWAY_ENVIRONMENT) or config('DATABASE_URL', default='').startswith('postgresql://')
IS_DEVELOPMENT = config('DEBUG', default=not IS_RAILWAY, cast=bool)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = IS_DEVELOPMENT

# Allowed hosts
if IS_RAILWAY:
    ALLOWED_HOSTS = ['*']  # Railway handles domain routing
else:
    ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
]

LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.companies',
    'apps.taxpayers',
    'apps.sii',
    'apps.documents',
    'apps.expenses',
    'apps.forms',
    'apps.analytics',
    'apps.ai_assistant',
    'apps.tasks',
    'apps.notifications',
    'apps.rates',
    'apps.onboarding',
    'apps.whatsapp',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Add production-specific apps for Railway
if IS_RAILWAY:
    # Note: django_health_check not included in requirements.txt
    # Using simple health endpoint instead
    pass

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.TimezoneMiddleware',
    'apps.core.middleware.CompanyMiddleware',
]

# Add whitenoise for Railway
if IS_RAILWAY:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'fizko_django.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fizko_django.wsgi.application'

# Database configuration
if IS_RAILWAY:
    # Railway provides DATABASE_URL automatically
    DATABASES = {
        'default': dj_database_url.config(
            default=config('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Local development database
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='fizko_db'),
            'USER': config('DB_USER', default='fizko'),
            'PASSWORD': config('DB_PASSWORD', default='fizko_password'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'OPTIONS': {
                'connect_timeout': 20,
            },
            'CONN_MAX_AGE': 600,
        }
    }

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = config('LANGUAGE_CODE', default='es-cl')
TIME_ZONE = config('TIMEZONE', default='America/Santiago')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Static files storage for Railway
if IS_RAILWAY:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
if IS_DEVELOPMENT:
    # Development - allow all origins
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
    ]
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
    CORS_EXPOSE_HEADERS = ['Content-Type', 'X-CSRFToken']
else:
    # Production - specific origins for Railway
    CORS_ALLOWED_ORIGINS = config(
        'CORS_ALLOWED_ORIGINS',
        default='',
        cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
    )
    # Allow regex patterns for Vercel preview deployments
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.vercel\.app$",
    ]

CORS_ALLOW_CREDENTIALS = True

# CSRF Configuration
if IS_RAILWAY:
    CSRF_TRUSTED_ORIGINS = config(
        'CSRF_TRUSTED_ORIGINS',
        default='',
        cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
    )
else:
    CSRF_TRUSTED_ORIGINS = config(
        'CSRF_TRUSTED_ORIGINS',
        default='http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000',
        cast=lambda v: [s.strip() for s in v.split(',')]
    )

# Redis Configuration
REDIS_URL = config('REDIS_URL', default='redis://redis:6379/0')

# Cache Configuration
if IS_RAILWAY:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': config('REDIS_URL'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'fizko',
            'TIMEOUT': 300,  # 5 minutes
        }
    }

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default=REDIS_URL)
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='django-db')

# Celery task configuration
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Celery Beat
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULE = {}

# Celery routing - optimized for Railway
if IS_RAILWAY:
    CELERY_TASK_ROUTES = {
        'apps.sii.tasks.*': {'queue': 'sii'},
        'apps.documents.tasks.*': {'queue': 'documents'},
        'apps.whatsapp.tasks.*': {'queue': 'whatsapp'},
        'apps.forms.tasks.*': {'queue': 'default'},
        'apps.analytics.tasks.*': {'queue': 'default'},
        'apps.notifications.tasks.*': {'queue': 'default'},
    }
else:
    CELERY_TASK_ROUTES = {
        'apps.sii.tasks.*': {'queue': 'sii'},
        'apps.documents.tasks.*': {'queue': 'documents'},
        'apps.forms.tasks.*': {'queue': 'forms'},
        'apps.analytics.tasks.*': {'queue': 'analytics'},
        'apps.ai_assistant.tasks.*': {'queue': 'ai'},
        'apps.notifications.tasks.*': {'queue': 'notifications'},
        'apps.whatsapp.tasks.*': {'queue': 'whatsapp'},
    }

# Worker configuration
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Task time limits
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Security settings for Railway
if IS_RAILWAY:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
    CONN_MAX_AGE = 300

# SII Configuration
SII_BASE_URL = config('SII_BASE_URL', default='https://www.sii.cl')
SII_LOGIN_URL = config(
    'SII_LOGIN_URL',
    default='https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html'
)
SII_TIMEOUT = config('SII_TIMEOUT', default=30, cast=int)
SII_USE_REAL_SERVICE = config('SII_USE_REAL_SERVICE', default=IS_RAILWAY, cast=bool)

# OpenAI Configuration
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# Email Configuration
if IS_RAILWAY:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')

EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@fizko.cl')

# Selenium Configuration
CHROME_BINARY_PATH = config('CHROME_BINARY_PATH', default='/usr/bin/chromium')
CHROME_DRIVER_PATH = config('CHROME_DRIVER_PATH', default='/usr/bin/chromedriver')
HEADLESS_BROWSER = config('HEADLESS_BROWSER', default=True, cast=bool)

# Logging Configuration
LOG_LEVEL = config('LOG_LEVEL', default='INFO' if IS_RAILWAY else 'DEBUG')

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
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# WhatsApp/Kapso Configuration
KAPSO_API_BASE_URL = config('KAPSO_API_BASE_URL', default='https://app.kapso.ai/api/v1')
KAPSO_API_TOKEN = config('KAPSO_API_TOKEN', default='')
WHATSAPP_WEBHOOK_SECRET = config('WHATSAPP_WEBHOOK_SECRET', default='your-webhook-secret-here')

# WhatsApp Business Hours (default for new configs)
WHATSAPP_DEFAULT_BUSINESS_HOURS_START = config('WHATSAPP_BUSINESS_HOURS_START', default='09:00')
WHATSAPP_DEFAULT_BUSINESS_HOURS_END = config('WHATSAPP_BUSINESS_HOURS_END', default='18:00')

# Auto-responses settings
WHATSAPP_ENABLE_AUTO_RESPONSES = config('WHATSAPP_ENABLE_AUTO_RESPONSES', default=True, cast=bool)
WHATSAPP_AUTO_RESPONSE_DELAY = config('WHATSAPP_AUTO_RESPONSE_DELAY', default=30, cast=int)  # seconds

# Message limits and rate limiting
WHATSAPP_MAX_MESSAGE_LENGTH = config('WHATSAPP_MAX_MESSAGE_LENGTH', default=4096, cast=int)
WHATSAPP_RATE_LIMIT_PER_MINUTE = config('WHATSAPP_RATE_LIMIT_PER_MINUTE', default=60, cast=int)

# Webhook processing
WHATSAPP_WEBHOOK_TIMEOUT = config('WHATSAPP_WEBHOOK_TIMEOUT', default=30, cast=int)
WHATSAPP_WEBHOOK_MAX_RETRIES = config('WHATSAPP_WEBHOOK_MAX_RETRIES', default=3, cast=int)

# Cleanup settings
WHATSAPP_CLEANUP_WEBHOOK_EVENTS_DAYS = config('WHATSAPP_CLEANUP_WEBHOOK_EVENTS_DAYS', default=30, cast=int)
WHATSAPP_CLEANUP_TEST_EVENTS_DAYS = config('WHATSAPP_CLEANUP_TEST_EVENTS_DAYS', default=7, cast=int)

# Sentry configuration for error tracking (Railway only)
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN and SENTRY_DSN.startswith(('http://', 'https://')) and IS_RAILWAY:
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
        environment='railway-production' if IS_RAILWAY else 'development'
    )