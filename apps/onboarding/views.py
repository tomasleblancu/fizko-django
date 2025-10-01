from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import OnboardingStep, UserOnboarding, OnboardingProgress
from apps.accounts.models import UserProfile
from .serializers import (
    OnboardingStepSerializer,
    UserOnboardingSerializer,
    OnboardingProgressSerializer,
    CompleteStepSerializer
)


class OnboardingStepViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para pasos de onboarding (solo lectura)
    """
    queryset = OnboardingStep.objects.filter(is_active=True)
    serializer_class = OnboardingStepSerializer
    permission_classes = [IsAuthenticated]


class UserOnboardingViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar el onboarding del usuario
    """
    serializer_class = UserOnboardingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_email = self.request.user.email
        return UserOnboarding.objects.filter(user_email=user_email)

    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Obtiene el estado general del onboarding del usuario
        """
        user_email = request.user.email
        
        # Obtener pasos activos
        active_steps = OnboardingStep.objects.filter(is_active=True)
        
        # Obtener progreso del usuario
        user_onboarding = UserOnboarding.objects.filter(
            user_email=user_email,
            step__is_active=True
        )
        
        # Crear respuesta de estado
        total_steps = active_steps.count()
        completed_steps = user_onboarding.filter(status='completed').count()
        current_step_obj = user_onboarding.filter(
            Q(status='in_progress') | Q(status='not_started')
        ).first()

        # Verificar si existe un registro de finalización
        finalized_step = user_onboarding.filter(
            step__name='finalized'
        ).first()

        current_step = current_step_obj.step.step_order if current_step_obj else 1
        # El onboarding solo está completado si fue finalizado explícitamente
        is_completed = finalized_step is not None and finalized_step.status == 'completed'
        
        # Calcular qué pasos están completados
        completed_step_numbers = list(
            user_onboarding.filter(status='completed')
            .values_list('step__step_order', flat=True)
        )

        # Recopilar datos guardados de todos los pasos
        step_data_collection = {}
        for user_step in user_onboarding.filter(step_data__isnull=False):
            if user_step.step_data:
                step_key = f"step_{user_step.step.step_order}"
                step_data_collection[step_key] = {
                    'step_name': user_step.step.name,
                    'step_order': user_step.step.step_order,
                    'data': user_step.step_data,
                    'status': user_step.status,
                    'completed_at': user_step.completed_at.isoformat() if user_step.completed_at else None
                }

        return Response({
            'user_id': request.user.id,
            'is_completed': is_completed,
            'current_step': current_step,
            'completed_steps': completed_step_numbers,
            'step_data': step_data_collection,
            'total_steps': total_steps,
            'progress_percentage': (completed_steps / total_steps * 100) if total_steps > 0 else 0
        })

    @action(detail=False, methods=['post'])
    def complete(self, request):
        """
        Completa todo el onboarding del usuario
        """
        user_email = request.user.email
        
        # Completar todos los pasos pendientes
        pending_steps = UserOnboarding.objects.filter(
            user_email=user_email,
            status__in=['not_started', 'in_progress']
        )
        
        for step in pending_steps:
            step.complete_step()
        
        return Response({
            'message': 'Onboarding completed successfully',
            'completed_at': timezone.now()
        })
    
    @action(detail=False, methods=['post'])
    def finalize(self, request):
        """
        Finaliza el onboarding asegurándose de que la empresa esté creada
        SEGURIDAD: Siempre verifica credenciales antes de asignar empresa
        """
        user_email = request.user.email
        
        try:
            # Buscar datos del paso de empresa completado
            company_step_data = UserOnboarding.objects.filter(
                user_email=user_email,
                step__name='company',
                status='completed'
            ).first()
            
            if not company_step_data or not company_step_data.step_data:
                return Response({
                    'error': 'NO_COMPANY_DATA',
                    'message': 'No se encontraron datos de empresa en el onboarding. Complete el paso de empresa primero.',
                    'required_fields': ['business_name', 'tax_id', 'password', 'email']
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # PASO CRÍTICO DE SEGURIDAD: Verificar credenciales ANTES de cualquier operación
            step_data = company_step_data.step_data
            credentials_valid = self._verify_sii_credentials(step_data)
            
            if credentials_valid.get('error'):
                return Response({
                    'error': 'INVALID_CREDENTIALS',
                    'message': 'No se puede finalizar onboarding con credenciales SII inválidas',
                    'details': credentials_valid.get('message'),
                    'credential_error': credentials_valid.get('error')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Solo después de verificar credenciales, verificar si ya tiene empresa
            from apps.companies.models import Company
            tax_id = step_data.get('tax_id')
            
            # Verificar si el usuario ya está asociado a esta empresa específica
            existing_user_company = Company.objects.filter(
                tax_id=tax_id,
                taxpayer_sii_credentials__user__email=user_email
            ).first()
            
            # if existing_user_company:
            #     return Response({
            #         'status': 'success',
            #         'message': 'Usuario ya tiene acceso a esta empresa',
            #         'company_id': existing_user_company.id,
            #         'company_name': existing_user_company.business_name,
            #         'verification_status': 'credentials_verified'
            #     })
            
            # Verificar si ya se creó la empresa durante el paso de credenciales
            company_creation_result = company_step_data.step_data.get('company_creation_result')
            
            if company_creation_result and company_creation_result.get('status') == 'success':
                # Empresa ya fue creada durante el update_step del paso de empresa
                company_result = company_creation_result
                message = 'Empresa fue creada exitosamente durante el proceso de onboarding'
            else:
                # Fallback: crear empresa si por alguna razón no se creó antes
                # (esto no debería pasar con el nuevo flujo, pero es seguridad adicional)
                company_result = self._create_or_assign_company_from_onboarding(request, step_data)
                
                if company_result.get('error'):
                    return Response(company_result, status=status.HTTP_400_BAD_REQUEST)
                
                # Actualizar step_data con resultado
                company_step_data.step_data['company_creation_result'] = company_result
                company_step_data.save()
                message = 'Empresa creada durante finalización del onboarding'
            
            # Marcar onboarding como completado
            self.complete(request)
            
            # INICIAR SINCRONIZACIONES DE DTES al finalizar onboarding
            company_id = None
            if company_result.get('company_data') and company_result['company_data'].get('company_id'):
                company_id = company_result['company_data']['company_id']
            elif existing_user_company:
                company_id = existing_user_company.id

            # Ejecutar las tareas de sincronización y creación de procesos al finalizar el onboarding
            initial_sync_result = None
            process_creation_result = None

            if company_id:
                # 1. Crear procesos tributarios según configuración del TaxPayer (PRIMERO)
                process_creation_result = self._create_taxpayer_processes(company_id)

                # 2. Sincronización inicial rápida (últimos 2 meses)
                # NOTA: Esta tarea disparará automáticamente la sincronización histórica completa al finalizar
                initial_sync_result = self._start_initial_dte_sync(company_id)

            # Marcar el onboarding como oficialmente finalizado
            finalized_step, created = OnboardingStep.objects.get_or_create(
                name='finalized',
                defaults={
                    'title': 'Onboarding Finalizado',
                    'step_order': 999,
                    'is_active': False  # No visible en el flujo normal
                }
            )

            # Crear registro de finalización para el usuario
            UserOnboarding.objects.update_or_create(
                user_email=user_email,
                step=finalized_step,
                defaults={
                    'status': 'completed',
                    'completed_at': timezone.now(),
                    'step_data': {
                        'finalized_at': timezone.now().isoformat(),
                        'company_created': company_id is not None,
                        'company_id': company_id
                    }
                }
            )

            return Response({
                'status': 'success',
                'message': message,
                'company_result': company_result,
                'sync_results': {
                    'initial_sync': initial_sync_result,
                    'process_creation': process_creation_result
                },
                'finalized_at': timezone.now(),
                'next_steps': 'Su historial contable reciente se está procesando. Una vez completado, se iniciará automáticamente la sincronización completa del historial. Puede comenzar a usar la plataforma con los datos recientes disponibles.'
            })
            
        except Exception as e:
            return Response({
                'error': 'FINALIZATION_ERROR',
                'message': f'Error finalizando onboarding: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['patch'])
    def update_step(self, request):
        """
        Actualizar el estado de un paso específico
        """
        user_email = request.user.email
        step_number = request.data.get('step')
        step_data = request.data.get('data', {})
        new_status = request.data.get('status', 'completed')
        
        if not step_number:
            return Response(
                {'error': 'Step number is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            step = OnboardingStep.objects.get(step_order=step_number, is_active=True)
            user_onboarding, created = UserOnboarding.objects.get_or_create(
                user_email=user_email,
                step=step,
                defaults={
                    'status': 'not_started',
                    'started_at': timezone.now()
                }
            )
            
            # Actualizar estado
            user_onboarding.status = new_status
            if new_status == 'completed':
                user_onboarding.completed_at = timezone.now()
                
                # SEGURIDAD CRÍTICA: Si es el paso de empresa, verificar credenciales SOLAMENTE
                if step.name == 'company' and step_data:
                    # Verificar credenciales antes de cualquier operación
                    credentials_valid = self._verify_sii_credentials(step_data)

                    if credentials_valid.get('error'):
                        return Response({
                            'error': 'INVALID_CREDENTIALS',
                            'message': 'No se puede completar el paso con credenciales SII inválidas',
                            'details': credentials_valid.get('message'),
                            'step': step.name
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # SOLO VERIFICAR - NO crear empresa aquí, eso ocurrirá en finalize()
                    # Guardar solo el resultado de verificación de credenciales
                    step_data['credential_verification'] = {
                        'status': 'verified',
                        'message': 'Credenciales SII verificadas exitosamente',
                        'verified_at': timezone.now().isoformat()
                    }

                    
            if step_data:
                user_onboarding.step_data.update(step_data)
            user_onboarding.save()
            
            return Response(UserOnboardingSerializer(user_onboarding).data)
            
        except OnboardingStep.DoesNotExist:
            return Response(
                {'error': 'Invalid step number'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _validate_company_data(self, step_data):
        """
        Valida datos requeridos para operaciones de empresa
        Returns: dict con 'success': True o 'error': mensaje
        """
        required_fields = ['business_name', 'tax_id', 'password', 'email']
        missing_fields = [field for field in required_fields if not step_data.get(field)]

        if missing_fields:
            return {
                'error': 'MISSING_REQUIRED_FIELDS',
                'message': f'Campos requeridos faltantes: {", ".join(missing_fields)}',
                'missing_fields': missing_fields
            }

        return {'success': True}

    def _get_company_models(self):
        """Retorna todos los imports necesarios para operaciones de empresa"""
        from apps.companies.models import Company
        from apps.taxpayers.models import TaxPayer, TaxpayerSiiCredentials
        from apps.accounts.models import Role, UserRole
        from apps.sii.api.servicev2 import SIIServiceV2

        return Company, TaxPayer, TaxpayerSiiCredentials, Role, UserRole, SIIServiceV2


    def _setup_user_role_for_company(self, user, company, role_name='owner'):
        """
        Maneja toda la lógica de asignación de roles para un usuario en una empresa
        """
        import logging
        logger = logging.getLogger(__name__)

        Company, TaxPayer, TaxpayerSiiCredentials, Role, UserRole, SIIServiceV2 = self._get_company_models()

        # Asegurar que los roles por defecto existen
        self._ensure_default_roles_exist()

        try:
            logger.info(f"🔍 Buscando rol '{role_name}' para usuario {user.email}")
            role = Role.objects.get(name=role_name)
            logger.info(f"✅ Rol '{role_name}' encontrado (ID: {role.id})")

            user_role, created = UserRole.objects.get_or_create(
                user=user,
                company=company,
                role=role,
                defaults={'active': True}
            )

            # Verificar que el rol se guardó correctamente
            if not user_role.active:
                user_role.active = True
                user_role.save()
                logger.warning(f"⚠️ Rol estaba inactivo, activado para {user.email}")

            action = "creado" if created else "ya existía"
            logger.info(f"✅ UserRole {action} - Usuario: {user.email}, Empresa: {company.business_name} (ID: {company.id}), Rol: {role_name}")

            # Verificación adicional
            verification = UserRole.objects.filter(
                user=user,
                company=company,
                role=role,
                active=True
            ).exists()

            if not verification:
                logger.error(f"❌ VERIFICACIÓN FALLÓ - UserRole no se encontró activo después de la creación")
                return {
                    'error': 'ROLE_VERIFICATION_FAILED',
                    'message': f'No se pudo verificar que el rol {role_name} se asignó correctamente'
                }

            logger.info(f"✅ Verificación exitosa - UserRole activo confirmado")

            return {
                'success': True,
                'role': role_name,
                'created': created,
                'user_role_id': user_role.id,
                'verification_passed': True
            }
        except Role.DoesNotExist:
            logger.error(f"❌ Rol '{role_name}' no existe en la base de datos")
            available_roles = list(Role.objects.values_list('name', flat=True))
            logger.error(f"📋 Roles disponibles: {available_roles}")
            return {
                'error': 'ROLE_NOT_FOUND',
                'message': f'Rol {role_name} no existe',
                'available_roles': available_roles
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado asignando rol: {str(e)}")
            return {
                'error': 'ROLE_ASSIGNMENT_ERROR',
                'message': f'Error inesperado: {str(e)}'
            }

    def _verify_sii_credentials(self, step_data):
        """
        Verifica las credenciales SII usando el servicio compartido
        Returns: dict con 'success': True o 'error': mensaje
        """
        try:
            from apps.companies.services import CompanyCreationService

            # Validar datos requeridos para verificación
            required_fields = ['tax_id', 'password']
            missing_fields = [field for field in required_fields if not step_data.get(field)]

            if missing_fields:
                return {
                    'error': 'MISSING_CREDENTIALS',
                    'message': f'Faltan credenciales requeridas: {", ".join(missing_fields)}'
                }

            tax_id = step_data['tax_id']
            password = step_data['password']

            # Usar el servicio compartido para validación
            result = CompanyCreationService.validate_sii_credentials(tax_id, password)

            if result['success']:
                return {
                    'success': True,
                    'message': result['message'],
                    'sii_data': result.get('taxpayer_data', {})
                }
            else:
                return {
                    'error': result.get('error', 'VALIDATION_ERROR'),
                    'message': result.get('message', 'Error validando credenciales')
                }

        except Exception as e:
            return {
                'error': 'VERIFICATION_ERROR',
                'message': f'Error verificando credenciales SII: {str(e)}'
            }

    def _create_or_assign_company_from_onboarding(self, request, step_data):
        """
        Crea nueva empresa o asigna usuario a empresa existente usando el servicio compartido
        SOLO después de verificar credenciales SII
        """
        try:
            # Validar datos requeridos usando método centralizado
            validation_result = self._validate_company_data(step_data)
            if validation_result.get('error'):
                return validation_result

            from apps.companies.services import CompanyCreationService

            # Extraer datos necesarios
            business_name = step_data['business_name']
            tax_id = step_data['tax_id']
            sii_password = step_data['password']
            email = step_data['email']
            mobile_phone = step_data.get('mobile_phone', '')

            # Usar el servicio compartido
            result = CompanyCreationService.create_company_from_sii_credentials(
                user=request.user,
                business_name=business_name,
                tax_id=tax_id,
                sii_password=sii_password,
                email=email,
                mobile_phone=mobile_phone
            )

            # Convertir la respuesta del servicio al formato esperado por el onboarding
            if result['success']:
                return {
                    'status': 'success',
                    'message': result['message'],
                    'company_data': result['company_data']
                }
            else:
                return {
                    'error': result.get('error', 'COMPANY_CREATION_ERROR'),
                    'message': result.get('message', 'Error desconocido'),
                    'details': result
                }

        except Exception as e:
            import traceback
            return {
                'error': 'COMPANY_ASSIGNMENT_ERROR',
                'message': f'Error asignando o creando empresa: {str(e)}',
                'traceback': traceback.format_exc()
            }
    
    def _ensure_default_roles_exist(self):
        """
        Asegura que los roles por defecto existan en el sistema
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
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'permissions': role_data['permissions'],
                    'is_active': True
                }
            )
            if created:
                print(f"✅ Rol '{role.name}' creado exitosamente")


    def _start_initial_dte_sync(self, company_id):
        """
        Inicia sincronización RÁPIDA de DTEs recientes para feedback inmediato
        Solo obtiene documentos de los últimos 2 meses para mostrar datos rápido
        """
        try:
            from datetime import date, timedelta
            from apps.companies.models import Company, BackgroundTaskTracker

            # Obtener la empresa
            company = Company.objects.get(id=company_id)
            
            # Calcular período de los últimos 2 meses para sync rápido
            today = date.today()
            fecha_hasta = today.strftime('%Y-%m-%d')
            
            # Ir 2 meses atrás
            fecha_desde = (today - timedelta(days=60)).replace(day=1).strftime('%Y-%m-%d')
            
            # Importar la tarea de Celery para sincronización de PERÍODO
            from apps.sii.tasks import sync_sii_documents_task
            
            # Enviar tarea a Celery para procesamiento asíncrono RÁPIDO
            rut_parts = company.tax_id.split('-')
            task_result = sync_sii_documents_task.delay(
                company_rut=rut_parts[0],  # RUT sin guión
                company_dv=rut_parts[1] if len(rut_parts) > 1 else 'K',  # DV
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                user_email=getattr(self.request.user, 'email', 'system@fizko.com'),
                priority='high',  # Alta prioridad por ser onboarding
                description=f'Sincronización inicial rápida onboarding - {company.business_name}',
                trigger_full_sync=True  # CRUCIAL: Disparar sync completo al finalizar
            )

            # CREAR TRACKER para monitorear progreso
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
                'message': 'Sincronización RÁPIDA de DTEs iniciada - se disparará historial completo al finalizar',
                'task_id': task_result.id,
                'company_id': company_id,
                'sync_type': 'recent_period_with_full_trigger',
                'sync_period': {
                    'fecha_desde': fecha_desde,
                    'fecha_hasta': fecha_hasta,
                    'description': 'Últimos 2 meses'
                },
                'estimated_completion': '2-5 minutos para inicial, luego 15-30 minutos para historial completo',
                'note': 'Sincronización rápida para mostrar datos inmediatos. Al finalizar, se disparará automáticamente la sincronización COMPLETA del historial desde inicio de actividades.'
            }
            
        except Company.DoesNotExist:
            return {
                'error': 'COMPANY_NOT_FOUND',
                'message': f'No se encontró la empresa con ID {company_id}',
                'sync_status': 'failed'
            }
            
        except ImportError as e:
            return {
                'error': 'TASK_IMPORT_ERROR', 
                'message': f'Error importando tareas SII: {str(e)}',
                'sync_status': 'failed'
            }
            
        except Exception as e:
            import traceback
            return {
                'error': 'DTE_SYNC_ERROR',
                'message': f'Error iniciando sincronización de DTEs: {str(e)}',
                'sync_status': 'failed',
                'traceback': traceback.format_exc()
            }

    def _start_complete_historical_sync(self, company_id):
        """
        Inicia sincronización COMPLETA del historial de DTEs y formularios tributarios
        Obtiene TODOS los documentos y formularios desde el inicio de actividades
        Se ejecuta al FINALIZAR el onboarding completo
        """
        try:
            from apps.companies.models import Company, BackgroundTaskTracker

            # Obtener la empresa
            company = Company.objects.get(id=company_id)
            
            # Importar las tareas de Celery para sincronización COMPLETA
            from apps.sii.tasks import sync_sii_documents_full_history_task, sync_all_historical_forms_task

            # Enviar tareas a Celery para procesamiento asíncrono COMPLETO
            rut_parts = company.tax_id.split('-')
            company_rut = rut_parts[0]  # RUT sin guión
            company_dv = rut_parts[1] if len(rut_parts) > 1 else 'K'  # DV
            user_email = getattr(self.request.user, 'email', 'system@fizko.com')

            # 1. Sincronización de documentos DTEs históricos
            documents_task_result = sync_sii_documents_full_history_task.delay(
                company_rut=company_rut,
                company_dv=company_dv,
                user_email=user_email
            )

            # CREAR TRACKER para documentos históricos
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

            # CREAR TRACKER para formularios históricos
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
                'message': 'Sincronización COMPLETA del historial iniciada - procesando TODOS los documentos y formularios históricos',
                'documents_task_id': documents_task_result.id,
                'forms_task_id': forms_task_result.id,
                'company_id': company_id,
                'sync_type': 'full_history',
                'sync_period': {
                    'description': 'Historial completo desde inicio de actividades'
                },
                'estimated_completion': '20-40 minutos (depende del volumen histórico)',
                'note': 'Esta sincronización obtendrá todos los DTEs y formularios tributarios disponibles desde el inicio de actividades de la empresa',
                'tasks': {
                    'documents': {
                        'task_id': documents_task_result.id,
                        'description': 'Documentos electrónicos (DTEs) históricos'
                    },
                    'forms': {
                        'task_id': forms_task_result.id,
                        'description': 'Formularios tributarios (F29) históricos'
                    }
                }
            }
            
        except Company.DoesNotExist:
            return {
                'error': 'COMPANY_NOT_FOUND',
                'message': f'No se encontró la empresa con ID {company_id}',
                'sync_status': 'failed'
            }
            
        except ImportError as e:
            return {
                'error': 'TASK_IMPORT_ERROR', 
                'message': f'Error importando tareas SII: {str(e)}',
                'sync_status': 'failed'
            }
            
        except Exception as e:
            import traceback
            return {
                'error': 'HISTORICAL_SYNC_ERROR',
                'message': f'Error iniciando sincronización histórica completa: {str(e)}',
                'sync_status': 'failed',
                'traceback': traceback.format_exc()
            }

    def _create_taxpayer_processes(self, company_id):
        """
        Crea los procesos tributarios según la configuración del TaxPayer
        Se ejecuta al FINALIZAR el onboarding para preparar los procesos tributarios
        """
        try:
            from apps.companies.models import Company, BackgroundTaskTracker

            # Verificar que la empresa tenga TaxPayer
            company = Company.objects.get(id=company_id)

            # Verificar que exista el TaxPayer
            if not hasattr(company, 'taxpayer'):
                return {
                    'status': 'skipped',
                    'message': 'Empresa sin TaxPayer configurado',
                    'company_id': company_id
                }

            # Importar la tarea de Celery para crear procesos
            from apps.tasks.tasks.process_management import create_processes_from_taxpayer_settings

            # Enviar tarea a Celery para procesamiento asíncrono
            task_result = create_processes_from_taxpayer_settings.delay(company_id=company_id)

            # CREAR TRACKER para monitorear progreso
            BackgroundTaskTracker.create_for_task(
                company=company,
                task_result=task_result,
                task_name='create_processes_from_taxpayer_settings',
                display_name='Creando procesos tributarios',
                metadata={'company_id': company_id}
            )

            # Obtener configuración actual del TaxPayer para informar
            taxpayer = company.taxpayer
            process_settings = taxpayer.get_process_settings()

            enabled_processes = []
            if process_settings.get('f29_monthly', False):
                enabled_processes.append('F29 Mensual')
            if process_settings.get('f22_annual', False):
                enabled_processes.append('F22 Anual')
            if process_settings.get('f3323_quarterly', False):
                enabled_processes.append('F3323 Trimestral')

            return {
                'status': 'success',
                'message': 'Creación de procesos tributarios iniciada',
                'task_id': task_result.id,
                'company_id': company_id,
                'taxpayer_rut': company.tax_id,
                'process_settings': process_settings,
                'enabled_processes': enabled_processes,
                'description': f'Creando procesos para: {", ".join(enabled_processes) if enabled_processes else "Ninguno habilitado"}'
            }

        except Company.DoesNotExist:
            return {
                'error': 'COMPANY_NOT_FOUND',
                'message': f'No se encontró empresa con ID {company_id}',
                'process_creation_status': 'failed'
            }
        except ImportError as e:
            return {
                'error': 'CELERY_IMPORT_ERROR',
                'message': f'Error importando tarea de creación de procesos: {str(e)}',
                'process_creation_status': 'failed'
            }
        except Exception as e:
            import traceback
            return {
                'error': 'PROCESS_CREATION_ERROR',
                'message': f'Error iniciando creación de procesos: {str(e)}',
                'process_creation_status': 'failed',
                'traceback': traceback.format_exc()
            }

    @action(detail=False, methods=['post'])
    def fix_incomplete_onboarding(self, request):
        """
        Función de utilidad para auto-completar pasos faltantes
        SOLO para usuarios que ya han creado empresa pero tienen pasos incompletos
        """
        user_email = request.user.email
        
        # Verificar si el usuario ya tiene empresa creada
        from apps.companies.models import Company
        user_companies = Company.objects.filter(
            taxpayer_sii_credentials__user__email=user_email
        )
        
        if not user_companies.exists():
            return Response({
                'error': 'USER_WITHOUT_COMPANY',
                'message': 'El usuario no tiene empresas creadas. Complete el onboarding normalmente.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Auto-completar pasos faltantes
        all_required_steps = OnboardingStep.objects.filter(
            is_active=True, 
            is_required=True
        )
        
        fixed_steps = []
        for step in all_required_steps:
            user_step, created = UserOnboarding.objects.get_or_create(
                user_email=user_email,
                step=step,
                defaults={
                    'status': 'completed',
                    'started_at': timezone.now(),
                    'completed_at': timezone.now(),
                    'step_data': {'auto_completed': True, 'reason': 'Fixed incomplete onboarding for existing company user'}
                }
            )
            
            if created or user_step.status != 'completed':
                if not created:
                    user_step.status = 'completed'
                    user_step.completed_at = timezone.now()
                    user_step.step_data['auto_completed'] = True
                    user_step.step_data['reason'] = 'Fixed incomplete onboarding for existing company user'
                    user_step.save()
                
                fixed_steps.append({
                    'step_order': step.step_order,
                    'name': step.name,
                    'title': step.title,
                    'action': 'created' if created else 'completed'
                })
        
        return Response({
            'status': 'success',
            'message': f'Se auto-completaron {len(fixed_steps)} pasos de onboarding',
            'fixed_steps': fixed_steps,
            'company_count': user_companies.count()
        })

    @action(detail=False, methods=['get'])
    def needs_onboarding(self, request):
        """
        Verifica si el usuario necesita completar onboarding
        El onboarding se puede saltar si:
        1. El usuario tiene skip_onboarding = True en su perfil (usuarios invitados)
        2. O si fue finalizado explícitamente
        """
        user_email = request.user.email

        # Verificar si el usuario tiene skip_onboarding activado
        skip_onboarding = False
        try:
            user_profile = UserProfile.objects.get(user=request.user)
            skip_onboarding = user_profile.skip_onboarding
        except UserProfile.DoesNotExist:
            # Si no existe perfil, crear uno por defecto
            UserProfile.objects.create(user=request.user, skip_onboarding=False)
            skip_onboarding = False

        # Si skip_onboarding es True, el usuario no necesita onboarding
        if skip_onboarding:
            return Response({
                'needs_onboarding': False,
                'reason': 'invited_user',
                'skip_onboarding': True,
                'required_steps': 0,
                'completed_required_steps': 0,
                'missing_steps': [],
                'is_finalized': False
            })

        # Verificar si existe un registro de finalización
        finalized_step = UserOnboarding.objects.filter(
            user_email=user_email,
            step__name='finalized',
            status='completed'
        ).first()

        # El onboarding solo está completado si fue finalizado explícitamente
        is_completed = finalized_step is not None
        needs_onboarding = not is_completed

        # Obtener información de pasos para debug
        required_steps = OnboardingStep.objects.filter(
            is_active=True,
            is_required=True
        ).count()

        completed_required_steps = UserOnboarding.objects.filter(
            user_email=user_email,
            step__is_active=True,
            step__is_required=True,
            status='completed'
        ).count()

        # Debug info para troubleshooting
        missing_steps = []
        if needs_onboarding:
            if not finalized_step:
                missing_steps.append({
                    'step_order': 4,
                    'name': 'finalize',
                    'title': 'Finalizar onboarding',
                    'current_status': 'not_started'
                })

            # También incluir pasos regulares que falten
            all_required_steps = OnboardingStep.objects.filter(
                is_active=True,
                is_required=True
            ).order_by('step_order')

            for step in all_required_steps:
                user_step = UserOnboarding.objects.filter(
                    user_email=user_email,
                    step=step
                ).first()
                if not user_step or user_step.status != 'completed':
                    missing_steps.append({
                        'step_order': step.step_order,
                        'name': step.name,
                        'title': step.title,
                        'current_status': user_step.status if user_step else 'not_started'
                    })

        return Response({
            'needs_onboarding': needs_onboarding,
            'reason': 'finalization_check' if not skip_onboarding else None,
            'skip_onboarding': skip_onboarding,
            'required_steps': required_steps,
            'completed_required_steps': completed_required_steps,
            'missing_steps': missing_steps,
            'is_finalized': is_completed
        })


class OnboardingProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver el progreso de onboarding (solo lectura)
    """
    serializer_class = OnboardingProgressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_email = self.request.user.email
        return OnboardingProgress.objects.filter(user_email=user_email)


@api_view(['POST'])
@permission_classes([])
def test_onboarding_company_integration(request):
    """
    Vista de prueba para probar la integración de onboarding con creación de empresa
    """
    try:
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Crear usuario de prueba
        test_user, _ = User.objects.get_or_create(
            username='onboarding_test_user',
            defaults={
                'email': 'onboarding_test@fizko.com',
                'first_name': 'Onboarding',
                'last_name': 'Test'
            }
        )
        
        # Simular datos de empresa del onboarding
        company_data = {
            'business_name': 'Empresa Onboarding Test',
            'tax_id': '77794858-k',  # Usar RUT conocido de pruebas
            'password': 'SiiPfufl574@#',  # Usar contraseña conocida
            'email': 'test@onboarding.cl',
            'mobile_phone': '+56912345678'
        }
        
        # Simular request con usuario
        request.user = test_user
        
        # Crear instancia de UserOnboardingViewSet
        viewset = UserOnboardingViewSet()
        
        # Probar método de creación de empresa
        result = viewset._create_company_from_onboarding(request, company_data)
        
        return Response({
            'status': 'success',
            'message': 'Prueba de integración onboarding-empresa completada',
            'test_user': test_user.username,
            'company_data_sent': company_data,
            'creation_result': result,
            'timestamp': timezone.now()
        })
        
    except Exception as e:
        import traceback
        return Response({
            'error': 'TEST_ERROR',
            'message': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': timezone.now()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)