"""
Servicios compartidos para gestión de empresas
"""
import logging
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class CompanyCreationService:
    """
    Servicio centralizado para crear empresas con credenciales SII
    Reutilizable tanto en onboarding como en settings
    """

    @staticmethod
    def validate_sii_credentials(tax_id, password):
        """
        Valida credenciales SII sin crear empresa
        Returns: dict con 'success': True/False y detalles
        """
        try:
            from apps.sii.api.servicev2 import SIIServiceV2

            # Crear servicio temporal para validación
            sii_service = SIIServiceV2.crear_con_password(
                tax_id=tax_id,
                password=password,
                validar_cookies=True,
                auto_relogin=False  # Solo validar, no mantener sesión
            )

            # Intentar consultar datos del contribuyente
            response = sii_service.consultar_contribuyente()

            if response.get('status') != 'success':
                return {
                    'success': False,
                    'error': 'INVALID_CREDENTIALS',
                    'message': response.get('message', 'Credenciales SII inválidas')
                }

            return {
                'success': True,
                'message': 'Credenciales SII válidas',
                'taxpayer_data': response.get('datos_contribuyente', {})
            }

        except Exception as e:
            logger.error(f"Error validating SII credentials: {str(e)}")
            return {
                'success': False,
                'error': 'VALIDATION_ERROR',
                'message': f'Error validando credenciales: {str(e)}'
            }

    @staticmethod
    def create_company_from_sii_credentials(user, business_name, tax_id, sii_password, email=None, mobile_phone=None):
        """
        Crea una empresa completa con credenciales SII

        Args:
            user: Usuario Django que será owner
            business_name: Nombre comercial elegido por el usuario
            tax_id: RUT con formato XX.XXX.XXX-X
            sii_password: Contraseña SII
            email: Email de contacto (opcional, usa el del usuario si no se proporciona)
            mobile_phone: Teléfono móvil (opcional)

        Returns:
            dict con status, message y company_data
        """
        try:
            with transaction.atomic():
                # 1. Validar credenciales SII primero
                validation_result = CompanyCreationService.validate_sii_credentials(tax_id, sii_password)

                if not validation_result['success']:
                    return validation_result

                # 2. Verificar si la empresa ya existe
                from apps.companies.models import Company
                from apps.taxpayers.models import TaxPayer, TaxpayerSiiCredentials
                from apps.accounts.models import Role, UserRole

                existing_company = Company.objects.filter(tax_id=tax_id).first()

                if existing_company:
                    return CompanyCreationService._assign_user_to_existing_company(
                        user, existing_company, sii_password
                    )

                # 3. Crear nueva empresa
                return CompanyCreationService._create_new_company(
                    user, business_name, tax_id, sii_password, email,
                    mobile_phone, validation_result['taxpayer_data']
                )

        except Exception as e:
            logger.error(f"Error creating company: {str(e)}")
            return {
                'success': False,
                'error': 'COMPANY_CREATION_ERROR',
                'message': f'Error interno: {str(e)}'
            }

    @staticmethod
    def _assign_user_to_existing_company(user, existing_company, sii_password):
        """
        Asigna usuario a empresa existente
        """
        try:
            from apps.taxpayers.models import TaxpayerSiiCredentials
            from apps.accounts.models import UserRole

            # Verificar si ya tiene credenciales
            existing_credentials = TaxpayerSiiCredentials.objects.filter(
                company=existing_company,
                user=user
            ).first()

            if existing_credentials:
                return {
                    'success': True,
                    'message': 'Usuario ya tiene acceso a esta empresa',
                    'company_data': {
                        'company_id': existing_company.id,
                        'tax_id': existing_company.tax_id,
                        'business_name': existing_company.business_name,
                        'existing_company': True,
                        'user_already_assigned': True
                    }
                }

            # Crear credenciales para el usuario
            credentials = TaxpayerSiiCredentials.objects.create(
                company=existing_company,
                user=user,
                tax_id=existing_company.tax_id
            )
            credentials.set_password(sii_password)
            credentials.save()

            # Determinar rol: owner si no hay owners, sino admin
            existing_owners = UserRole.objects.filter(
                company=existing_company,
                role__name='owner',
                active=True
            ).count()

            role_name = 'owner' if existing_owners == 0 else 'admin'
            role_result = CompanyCreationService._setup_user_role(user, existing_company, role_name)

            if role_result.get('error'):
                return role_result

            return {
                'success': True,
                'message': 'Usuario asignado a empresa existente',
                'company_data': {
                    'company_id': existing_company.id,
                    'tax_id': existing_company.tax_id,
                    'business_name': existing_company.business_name,
                    'existing_company': True,
                    'user_assigned': True,
                    'user_role': role_name
                }
            }

        except Exception as e:
            logger.error(f"Error assigning user to existing company: {str(e)}")
            return {
                'success': False,
                'error': 'USER_ASSIGNMENT_ERROR',
                'message': f'Error asignando usuario: {str(e)}'
            }

    @staticmethod
    def _create_new_company(user, business_name, tax_id, sii_password, email, mobile_phone, taxpayer_data):
        """
        Crea nueva empresa desde cero
        """
        try:
            from apps.companies.models import Company
            from apps.taxpayers.models import TaxPayer, TaxpayerSiiCredentials
            from apps.sii.api.servicev2 import SIIServiceV2

            # Obtener datos completos del contribuyente del SII
            sii_service = SIIServiceV2.crear_con_password(
                tax_id=tax_id,
                password=sii_password,
                validar_cookies=True,
                auto_relogin=True
            )

            response = sii_service.consultar_contribuyente()
            datos_sii = response.get('datos_contribuyente', {})
            contribuyente_data = datos_sii.get('contribuyente', {})

            # Usar email del usuario si no se proporciona
            if not email:
                email = user.email

            # Crear Company
            company_data = {
                'tax_id': tax_id,
                'business_name': business_name,
                'display_name': business_name,
                'email': contribuyente_data.get('eMail', email).strip() if contribuyente_data.get('eMail') else email,
                'mobile_phone': contribuyente_data.get('telefonoMovil', mobile_phone or '').strip() if contribuyente_data.get('telefonoMovil') else mobile_phone or '',
                'person_company': 'EMPRESA' if contribuyente_data.get('personaEmpresa') == 'EMPRESA' else 'PERSONA',
                'electronic_biller': True,
                'is_active': True,
                'preferred_currency': 'CLP',
                'time_zone': 'America/Santiago',
                'notify_new_documents': True,
                'notify_tax_deadlines': True,
                'notify_system_updates': True
            }

            company = Company.objects.create(**company_data)

            # Crear TaxPayer
            rut, dv = tax_id.split('-')
            taxpayer = TaxPayer.objects.create(
                company=company,
                rut=rut,
                dv=dv.upper(),
                tax_id=tax_id
            )

            # Sincronizar con datos del SII
            taxpayer.sync_from_sii_data(datos_sii)

            # Configurar procesos por defecto
            taxpayer.update_process_settings({
                'f29_monthly': True,
                'f22_annual': True,
                'f3323_quarterly': False
            })

            taxpayer.save()

            # Sincronizar datos de company desde taxpayer
            company.sync_taxpayer_data()
            company.save()

            # Almacenar credenciales
            credentials = TaxpayerSiiCredentials.objects.create(
                company=company,
                user=user,
                tax_id=tax_id
            )
            credentials.set_password(sii_password)
            credentials.save()

            # Asignar rol de owner al usuario
            role_result = CompanyCreationService._setup_user_role(user, company, 'owner')
            if role_result.get('error'):
                return role_result

            # Iniciar todas las tareas de inicialización (igual que en onboarding finalize)
            initialization_results = CompanyCreationService._start_initialization_tasks(company.id, user.email)

            return {
                'success': True,
                'message': 'Empresa creada exitosamente',
                'company_data': {
                    'company_id': company.id,
                    'tax_id': company.tax_id,
                    'business_name': company.business_name,
                    'display_name': company.display_name,
                    'razon_social': taxpayer.razon_social,
                    'credentials_stored': True,
                    'user_role': 'owner',
                    'initialization_results': initialization_results
                }
            }

        except Exception as e:
            logger.error(f"Error creating new company: {str(e)}")
            return {
                'success': False,
                'error': 'NEW_COMPANY_ERROR',
                'message': f'Error creando empresa: {str(e)}'
            }

    @staticmethod
    def _setup_user_role(user, company, role_name='owner'):
        """
        Configura el rol del usuario en la empresa
        """
        try:
            from apps.accounts.models import Role, UserRole

            # Asegurar que los roles existen
            CompanyCreationService._ensure_default_roles_exist()

            role = Role.objects.get(name=role_name)

            user_role, created = UserRole.objects.get_or_create(
                user=user,
                company=company,
                role=role,
                defaults={'active': True}
            )

            if not user_role.active:
                user_role.active = True
                user_role.save()

            logger.info(f"✅ UserRole {'creado' if created else 'ya existía'} - Usuario: {user.email}, Empresa: {company.business_name}, Rol: {role_name}")

            return {
                'success': True,
                'role_created': created,
                'role_name': role_name
            }

        except Exception as e:
            logger.error(f"Error setting up user role: {str(e)}")
            return {
                'error': 'ROLE_SETUP_ERROR',
                'message': f'Error configurando rol: {str(e)}'
            }

    @staticmethod
    def _ensure_default_roles_exist():
        """
        Asegura que los roles por defecto existan
        """
        from apps.accounts.models import Role

        default_roles = [
            {
                'name': 'owner',
                'description': 'Propietario de la empresa con acceso completo',
                'permissions': {
                    'companies': ['view', 'edit', 'delete', 'manage_users'],
                    'documents': ['view', 'create', 'edit', 'delete'],
                    'forms': ['view', 'create', 'edit', 'submit'],
                    'analytics': ['view', 'export'],
                    'settings': ['view', 'edit'],
                    'users': ['view', 'invite', 'edit', 'remove'],
                    'billing': ['view', 'edit']
                }
            },
            {
                'name': 'admin',
                'description': 'Administrador con permisos amplios pero limitados',
                'permissions': {
                    'companies': ['view', 'edit'],
                    'documents': ['view', 'create', 'edit', 'delete'],
                    'forms': ['view', 'create', 'edit', 'submit'],
                    'analytics': ['view', 'export'],
                    'settings': ['view'],
                    'users': ['view', 'invite']
                }
            },
            {
                'name': 'user',
                'description': 'Usuario básico con permisos de solo lectura/uso',
                'permissions': {
                    'companies': ['view'],
                    'documents': ['view', 'create'],
                    'forms': ['view', 'create', 'submit'],
                    'analytics': ['view'],
                    'settings': ['view'],
                    'users': ['view']
                }
            }
        ]

        for role_data in default_roles:
            Role.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'permissions': role_data['permissions'],
                    'is_active': True
                }
            )

    @staticmethod
    def _start_initialization_tasks(company_id, user_email):
        """
        Inicia todas las tareas de inicialización (igual que en onboarding finalize)
        1. Crear procesos tributarios
        2. Sincronización inicial (últimos 2 meses)
        3. Sincronización histórica completa
        """
        results = {
            'process_creation': None,
            'initial_sync': None,
            'historical_sync': None
        }

        try:
            from apps.companies.models import Company

            company = Company.objects.get(id=company_id)
            logger.info(f"🚀 Iniciando tareas de inicialización para empresa {company.business_name}")

            # 1. Crear procesos tributarios según configuración del TaxPayer
            results['process_creation'] = CompanyCreationService._create_taxpayer_processes(company_id)

            # 2. Sincronización inicial rápida (últimos 2 meses)
            results['initial_sync'] = CompanyCreationService._start_initial_dte_sync(company_id, user_email)

            # 3. Sincronización histórica completa (todo el historial)
            results['historical_sync'] = CompanyCreationService._start_complete_historical_sync(company_id, user_email)

            logger.info(f"✅ Tareas de inicialización configuradas para {company.business_name}")
            return results

        except Exception as e:
            logger.error(f"Error starting initialization tasks: {str(e)}")
            return {
                'process_creation': {'error': str(e)},
                'initial_sync': {'error': str(e)},
                'historical_sync': {'error': str(e)}
            }

    @staticmethod
    def _create_taxpayer_processes(company_id):
        """
        Crea los procesos tributarios según la configuración del TaxPayer
        """
        try:
            from apps.companies.models import Company, BackgroundTaskTracker
            from apps.tasks.tasks.process_management import create_processes_from_taxpayer_settings

            company = Company.objects.get(id=company_id)

            # Verificar que exista el TaxPayer
            if not hasattr(company, 'taxpayer'):
                return {
                    'status': 'skipped',
                    'message': 'Empresa sin TaxPayer configurado'
                }

            # Enviar tarea a Celery
            task_result = create_processes_from_taxpayer_settings.delay(company_id=company_id)

            # Crear tracker para monitoreo
            BackgroundTaskTracker.create_for_task(
                company=company,
                task_result=task_result,
                task_name='create_processes_from_taxpayer_settings',
                display_name='Creando procesos tributarios',
                metadata={'company_id': company_id}
            )

            return {
                'status': 'success',
                'message': 'Creación de procesos tributarios iniciada',
                'task_id': task_result.id
            }

        except Exception as e:
            logger.error(f"Error creating taxpayer processes: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error creando procesos: {str(e)}'
            }

    @staticmethod
    def _start_initial_dte_sync(company_id, user_email):
        """
        Inicia sincronización inicial rápida (últimos 2 meses)
        """
        try:
            from apps.companies.models import Company, BackgroundTaskTracker
            from apps.sii.tasks import sync_sii_documents_task

            company = Company.objects.get(id=company_id)

            # Calcular período de los últimos 2 meses
            today = date.today()
            fecha_hasta = today.strftime('%Y-%m-%d')
            fecha_desde = (today - timedelta(days=60)).replace(day=1).strftime('%Y-%m-%d')

            rut_parts = company.tax_id.split('-')
            task_result = sync_sii_documents_task.delay(
                company_rut=rut_parts[0],
                company_dv=rut_parts[1] if len(rut_parts) > 1 else 'K',
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                user_email=user_email,
                priority='high',
                description=f'Sincronización inicial - {company.business_name}',
                trigger_full_sync=True
            )

            # Crear tracker para monitoreo
            BackgroundTaskTracker.create_for_task(
                company=company,
                task_result=task_result,
                task_name='sync_sii_documents_task',
                display_name='Sincronizando documentos SII',
                metadata={
                    'company_id': company_id,
                    'sync_type': 'initial',
                    'fecha_desde': fecha_desde,
                    'fecha_hasta': fecha_hasta
                }
            )

            return {
                'status': 'success',
                'message': 'Sincronización inicial iniciada',
                'task_id': task_result.id,
                'sync_period': f'{fecha_desde} a {fecha_hasta}'
            }

        except Exception as e:
            logger.error(f"Error starting initial sync: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error en sincronización inicial: {str(e)}'
            }

    @staticmethod
    def _start_complete_historical_sync(company_id, user_email):
        """
        Inicia sincronización histórica completa (todo el historial)
        """
        try:
            from apps.companies.models import Company, BackgroundTaskTracker
            from apps.sii.tasks import sync_sii_documents_full_history_task, sync_all_historical_forms_task

            company = Company.objects.get(id=company_id)

            # Obtener partes del RUT
            rut_parts = company.tax_id.split('-')
            company_rut = rut_parts[0]
            company_dv = rut_parts[1] if len(rut_parts) > 1 else 'K'

            # 1. Sincronización de documentos DTEs históricos
            documents_task_result = sync_sii_documents_full_history_task.delay(
                company_rut=company_rut,
                company_dv=company_dv,
                user_email=user_email
            )

            # Crear tracker para documentos históricos
            BackgroundTaskTracker.create_for_task(
                company=company,
                task_result=documents_task_result,
                task_name='sync_sii_documents_full_history_task',
                display_name='Sincronizando historial completo SII',
                metadata={
                    'company_id': company_id,
                    'sync_type': 'full_history',
                    'task_type': 'documents'
                }
            )

            # 2. Sincronización de formularios tributarios históricos
            forms_task_result = sync_all_historical_forms_task.delay(
                company_rut=company_rut,
                company_dv=company_dv,
                user_email=user_email,
                form_type='f29'
            )

            # Crear tracker para formularios históricos
            BackgroundTaskTracker.create_for_task(
                company=company,
                task_result=forms_task_result,
                task_name='sync_all_historical_forms_task',
                display_name='Sincronizando formularios históricos',
                metadata={
                    'company_id': company_id,
                    'sync_type': 'full_history',
                    'task_type': 'forms',
                    'form_type': 'f29'
                }
            )

            return {
                'status': 'success',
                'message': 'Sincronización histórica completa iniciada',
                'documents_task_id': documents_task_result.id,
                'forms_task_id': forms_task_result.id
            }

        except Exception as e:
            logger.error(f"Error starting historical sync: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error en sincronización histórica: {str(e)}'
            }