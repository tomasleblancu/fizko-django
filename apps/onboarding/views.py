from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import OnboardingStep, UserOnboarding
# OnboardingProgress temporalmente deshabilitado (vista de BD no existe)
from apps.accounts.models import UserProfile
from .serializers import (
    OnboardingStepSerializer,
    UserOnboardingSerializer,
    # OnboardingProgressSerializer,  # Disabled
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
        return UserOnboarding.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Obtiene el estado general del onboarding del usuario
        """
        # Obtener pasos activos
        active_steps = OnboardingStep.objects.filter(is_active=True)

        # Obtener progreso del usuario
        user_onboarding = UserOnboarding.objects.filter(
            user=request.user,
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
        # Completar todos los pasos pendientes
        pending_steps = UserOnboarding.objects.filter(
            user=request.user,
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
        
        try:
            # Buscar datos del paso de empresa completado
            company_step_data = UserOnboarding.objects.filter(
                user=request.user,
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
                taxpayer_sii_credentials__user=request.user
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

            # Obtener company_id y los resultados de inicialización que ya se dispararon automáticamente
            company_id = None
            initialization_results = None

            if company_result.get('company_data'):
                company_id = company_result['company_data'].get('company_id')
                # Las tareas ya fueron creadas por CompanyCreationService, obtener sus resultados
                initialization_results = company_result['company_data'].get('initialization_results')
            elif existing_user_company:
                company_id = existing_user_company.id

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
                user=request.user,
                step=finalized_step,
                defaults={
                    'user_email': request.user.email,
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
                'sync_results': initialization_results,  # Resultados de las tareas ya creadas por el servicio
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
                user=request.user,
                step=step,
                defaults={
                    'user_email': request.user.email,
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


    @action(detail=False, methods=['post'])
    def fix_incomplete_onboarding(self, request):
        """
        Función de utilidad para auto-completar pasos faltantes
        SOLO para usuarios que ya han creado empresa pero tienen pasos incompletos
        """
        
        # Verificar si el usuario ya tiene empresa creada
        from apps.companies.models import Company
        user_companies = Company.objects.filter(
            taxpayer_sii_credentials__user=request.user
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
                user=request.user,
                step=step,
                defaults={
                    'user_email': request.user.email,
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
            user=request.user,
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
            user=request.user,
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
                    user=request.user,
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


# class OnboardingProgressViewSet(viewsets.ReadOnlyModelViewSet):
#     """
#     ViewSet para ver el progreso de onboarding (solo lectura)
#     DISABLED: OnboardingProgress modelo no existe
#     """
#     serializer_class = OnboardingProgressSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         return OnboardingProgress.objects.filter(user=self.request.user)


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