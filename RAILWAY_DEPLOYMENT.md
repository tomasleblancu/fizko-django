# Deployment de Fizko en Railway

Esta guía explica cómo deployar la aplicación Fizko Django en Railway usando la arquitectura multi-service.

## Arquitectura de Deployment

La aplicación se deploya como **6 servicios separados**:

1. **Web Service** - Django API principal
2. **Worker SII** - Celery worker para integración SII
3. **Worker Documents** - Celery worker para documentos
4. **Worker General** - Celery workers para WhatsApp, forms, analytics, notifications
5. **Beat Service** - Celery Beat para tareas programadas
6. **Database** - PostgreSQL + Redis (servicios nativos)

## Pasos para Deployment

### 1. Crear Servicios en Railway

#### Base de Datos
1. Crear **PostgreSQL Database**
2. Crear **Redis Service**

#### Servicios de la Aplicación
Para cada servicio, crear desde el mismo repositorio GitHub:

1. **Web Service**
   - Source: Tu repositorio GitHub
   - Root Directory: `/fizko_django`
   - Start Command: `./scripts/start-web.sh`

2. **Worker SII**
   - Source: Mismo repositorio
   - Root Directory: `/fizko_django`
   - Start Command: `./scripts/start-worker-sii.sh`

3. **Worker Documents**
   - Source: Mismo repositorio
   - Root Directory: `/fizko_django` 
   - Start Command: `./scripts/start-worker-docs.sh`

4. **Worker General**
   - Source: Mismo repositorio
   - Root Directory: `/fizko_django`
   - Start Command: `./scripts/start-worker-general.sh`

5. **Beat Service**
   - Source: Mismo repositorio
   - Root Directory: `/fizko_django`
   - Start Command: `./scripts/start-beat.sh`

### 2. Variables de Entorno

Configurar en **TODOS** los servicios de aplicación:

#### Variables Automáticas (Railway)
- `DATABASE_URL` - Auto-generada por PostgreSQL service
- `REDIS_URL` - Auto-generada por Redis service
- `PORT` - Auto-generada (solo para Web Service)

#### Variables Manuales
```env
DJANGO_SETTINGS_MODULE=fizko_django.settings.railway
SECRET_KEY=tu-secret-key-super-seguro
DEBUG=False
SII_USE_REAL_SERVICE=true

# SII Integration
SII_TAX_ID=tu-rut
SII_PASSWORD=tu-password-sii

# OpenAI
OPENAI_API_KEY=tu-openai-api-key

# WhatsApp/Kapso
KAPSO_API_BASE_URL=https://app.kapso.ai/api/v1
KAPSO_API_TOKEN=tu-kapso-token
WHATSAPP_WEBHOOK_SECRET=tu-webhook-secret

# Opcional - Sentry
SENTRY_DSN=tu-sentry-dsn

# Opcional - SSL (solo si usas dominio custom)
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

### 3. Conectar Servicios

En Railway, conectar cada servicio de aplicación a:
- PostgreSQL Database (variable `DATABASE_URL`)
- Redis Service (variable `REDIS_URL`)

### 4. Deploy

1. Hacer push a tu repositorio GitHub
2. Railway auto-deploya cada servicio
3. Verificar logs de cada servicio

### 5. Verificación Post-Deploy

#### Web Service
- ✅ Healthcheck: `https://tu-web-service.railway.app/health/`
- ✅ Admin: `https://tu-web-service.railway.app/admin/`
- ✅ API: `https://tu-web-service.railway.app/api/v1/`

#### Workers
- ✅ Verificar logs sin errores de conexión
- ✅ Tareas de prueba funcionando

## Escalado

### Recursos por Servicio (Recomendado)
- **Web**: 1 GB RAM, 1 vCPU
- **Worker SII**: 512 MB RAM, 0.5 vCPU (concurrency=2)
- **Worker Docs**: 1 GB RAM, 1 vCPU (concurrency=4)
- **Worker General**: 512 MB RAM, 0.5 vCPU (concurrency=3)
- **Beat**: 256 MB RAM, 0.25 vCPU
- **PostgreSQL**: 1 GB RAM, 1 vCPU
- **Redis**: 256 MB RAM, 0.25 vCPU

### Auto-scaling
Railway puede auto-escalar servicios basado en:
- CPU usage
- Memory usage  
- Request rate (solo Web Service)

## Monitoreo

### Logs
```bash
# Via Railway CLI
railway logs --service web
railway logs --service worker-sii
railway logs --service worker-docs
railway logs --service worker-general
railway logs --service beat
```

### Métricas
- Railway Dashboard provee métricas automáticas
- CPU, Memory, Network por servicio
- Request rate y response time (Web Service)

### Health Checks
- Web Service: `/health/` endpoint automático
- Workers: Railway monitorea proceso activo
- DB/Redis: Health checks nativos

## Troubleshooting

### Problemas Comunes

1. **Database Connection Errors**
   - Verificar `DATABASE_URL` en todas las variables
   - Check PostgreSQL service status

2. **Celery Workers Not Processing**
   - Verificar `REDIS_URL` en workers
   - Check Redis service status
   - Verificar queue routing en settings

3. **Selenium/Chrome Issues**
   - Dockerfile incluye chromium y chromium-driver
   - Verificar SII worker logs específicamente

4. **Static Files Issues**
   - Whitenoise maneja archivos estáticos
   - `collectstatic` se ejecuta en startup

### Comandos Útiles

```bash
# Ejecutar migraciones manualmente
railway run python manage.py migrate

# Crear superuser
railway run python manage.py createsuperuser

# Shell Django
railway run python manage.py shell

# Verificar configuración
railway run python manage.py check --deploy
```

## Costos Estimados

Base Railway Team Plan ($20/month):
- **Web Service**: ~$15-25/month
- **Workers (4)**: ~$30-40/month total
- **PostgreSQL**: ~$10-15/month
- **Redis**: ~$5-10/month
- **Total**: ~$60-90/month

## Ventajas vs Docker Compose

### ✅ Ventajas
- Auto-scaling por servicio
- Zero-downtime deployments
- Built-in monitoring y metrics
- Managed databases (PostgreSQL/Redis)
- SSL/TLS automático
- CDN integrado
- Backup automático de DB

### ⚠️ Consideraciones
- Costo mayor que VPS simple
- Dependencia de Railway platform
- Menos control sobre infraestructura

## Migration desde Docker Compose

1. Backup de base de datos actual
2. Deploy servicios Railway
3. Restore backup en PostgreSQL Railway
4. Update DNS a Railway endpoints
5. Monitor y test funcionamiento

La migración es reversible manteniendo el docker-compose.yml para desarrollo local.