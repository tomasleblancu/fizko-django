# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fizko is an accounting and tax management platform for Chilean businesses. It consists of a Django backend that integrates with the Chilean tax authority (SII) through web automation and provides APIs for document management, tax forms processing, and financial analytics.

## Key Commands

### Development with Docker (Recommended)
```bash
# Start all services
docker-compose up -d

# Start with development profile (includes ngrok)
docker-compose --profile development up -d

# View logs
docker-compose logs -f [service_name]

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart [service_name]
```

### Django Management
```bash
# Run migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Collect static files
docker-compose exec django python manage.py collectstatic --noinput

# Django shell
docker-compose exec django python manage.py shell

# Run specific test
docker-compose exec django python manage.py test tests.test_file

# Create new app
docker-compose exec django python manage.py startapp app_name
```

### Testing
```bash
# Run all tests
docker-compose exec django pytest

# Run specific test file
docker-compose exec django pytest tests/test_sii_documents.py

# Run with coverage
docker-compose exec django pytest --cov=apps

# Run linting
docker-compose exec django flake8
docker-compose exec django black . --check
docker-compose exec django isort . --check-only
```

### Celery Tasks
```bash
# Monitor Celery tasks with Flower
open http://localhost:5555

# View Celery worker logs
docker-compose logs -f celery_sii
docker-compose logs -f celery_documents
docker-compose logs -f celery_default
docker-compose logs -f celery_whatsapp

# Restart Celery workers
docker-compose restart celery_sii celery_documents celery_default celery_whatsapp
```

### WhatsApp Integration (ngrok)
```bash
# Get public ngrok URL for webhooks
./scripts/get_ngrok_url.sh

# View ngrok dashboard
open http://localhost:4040

# Setup WhatsApp templates
docker-compose exec django python manage.py setup_whatsapp_templates
```

## Architecture

### Core Structure
```
fizko_django/
├── apps/                   # Django applications
│   ├── core/              # Core utilities and middleware
│   ├── accounts/          # User authentication and management
│   ├── companies/         # Company management
│   ├── taxpayers/         # Chilean taxpayer data
│   ├── sii/               # SII (Chilean IRS) integration
│   ├── documents/         # Electronic document management
│   ├── expenses/          # Expense tracking
│   ├── forms/             # Tax form processing (F29, F3323)
│   ├── analytics/         # Financial analytics
│   ├── ai_assistant/      # OpenAI integration
│   ├── tasks/             # Async task management
│   ├── notifications/     # Notification system
│   ├── rates/             # Exchange rates
│   ├── onboarding/        # User onboarding
│   └── whatsapp/          # WhatsApp API integration
├── fizko_django/          # Project settings
│   └── settings/          # Environment-specific settings
├── tests/                 # Test files
├── requirements/          # Python dependencies
└── scripts/               # Utility scripts
```

### SII Integration Architecture

The SII app has been restructured for robustness:

```
apps/sii/
├── api/                   # High-level API and views
├── rpa/                   # Selenium automation
├── parsers/               # Data parsing
├── services/              # Business logic services
├── tasks/                 # Celery tasks
├── utils/                 # Utilities and exceptions
├── views/                 # Django views
├── models.py              # Database models
├── serializers.py         # DRF serializers
├── services.py            # Main service orchestration (legacy)
└── urls.py                # URL routing
```

### Service Stack
- **PostgreSQL**: Main database (port 5432)
- **Redis**: Cache and Celery broker (port 6379)
- **Django**: Web application (port 8000)
- **Celery**: Async task processing (multiple workers by queue)
- **Flower**: Celery monitoring (port 5555)
- **ngrok**: Development tunnel for webhooks (port 4040 dashboard)

### Celery Queue Routing
- `sii`: SII-related tasks (2 workers)
- `documents`: Document processing (4 workers)
- `whatsapp`: WhatsApp messaging (2 workers)
- `default`: General tasks including forms, analytics, notifications (3 workers)
- **Celery Beat**: Periodic task scheduler using DatabaseScheduler

## Environment Variables

Required in `.env`:
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=fizko_db
DB_USER=fizko
DB_PASSWORD=fizko_password
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# SII Integration
SII_TAX_ID=your-rut
SII_PASSWORD=your-password

# OpenAI
OPENAI_API_KEY=your-api-key

# WhatsApp/Kapso
KAPSO_API_BASE_URL=https://app.kapso.ai/api/v1
KAPSO_API_TOKEN=your-token
WHATSAPP_WEBHOOK_SECRET=your-webhook-secret

# ngrok (optional)
NGROK_AUTHTOKEN=your-auth-token
NGROK_FIXED_URL=your-domain.ngrok-free.app
```

## Chilean Tax System (SII) Context

- **RUT**: Chilean tax ID (format: XX.XXX.XXX-X)
- **DTE**: Electronic Tax Documents (facturas, boletas, etc.)
- **F29**: Monthly VAT declaration form
- **F3323**: Simplified tax regime form
- **IVA**: Value Added Tax (19% standard rate)

The system automates:
1. SII authentication with session management
2. Document extraction and parsing
3. Tax form calculations
4. Deadline tracking and notifications

## API Endpoints

Main API groups:
- `/api/v1/auth/` - Authentication (JWT)
- `/api/v1/companies/` - Company management
- `/api/v1/sii/` - SII integration
- `/api/v1/documents/` - Document management
- `/api/v1/forms/` - Tax forms
- `/api/v1/analytics/` - Financial analytics
- `/api/v1/whatsapp/` - WhatsApp messaging
- `/admin/` - Django admin interface
- `/health/` - Health check endpoint

## Development Workflow

### Local Development
1. **Start services**: `docker-compose --profile development up -d`
2. **Run migrations**: `docker-compose exec django python manage.py migrate`
3. **Create superuser**: `docker-compose exec django python manage.py createsuperuser`
4. **Access admin**: http://localhost:8000/admin/
5. **Monitor tasks**: http://localhost:5555 (Flower)
6. **View logs**: `docker-compose logs -f django`

### Railway Production Deployment
The app is configured for multi-service deployment on Railway. See `RAILWAY_DEPLOYMENT.md` for complete deployment guide.

**Key Railway Files:**
- `railway.json` - Railway service configuration
- `Procfile` - Process definitions for different services
- `fizko_django/settings/railway.py` - Railway-specific settings
- `requirements/railway.txt` - Production dependencies
- `scripts/start-*.sh` - Service startup scripts

## Testing Approach

- **Unit tests**: `docker-compose exec django pytest tests/test_specific.py`
- **Integration tests with real SII**: Located in `tests/test_real_*.py`
- **Coverage report**: `docker-compose exec django pytest --cov=apps --cov-report=html`
- **Single test run**: `docker-compose exec django pytest tests/test_sii_documents.py::TestClassName::test_method_name`
- **Pre-commit hooks**: `pre-commit install` (includes black, isort, flake8, mypy)

## Important Notes

- The SII integration uses Selenium for web automation - ensure Chrome/Chromium is available
- Celery workers are organized by task type for optimal performance
- WhatsApp integration requires ngrok for local development webhooks
- All datetime handling uses America/Santiago timezone
- Session cookies are cached in Redis to minimize SII logins