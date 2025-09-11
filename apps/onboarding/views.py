from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import OnboardingStep, UserOnboarding, OnboardingProgress
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
        
        current_step = current_step_obj.step.step_order if current_step_obj else 1
        is_completed = completed_steps == total_steps
        
        # Calcular qué pasos están completados
        completed_step_numbers = list(
            user_onboarding.filter(status='completed')
            .values_list('step__step_order', flat=True)
        )
        
        return Response({
            'user_id': request.user.id,
            'is_completed': is_completed,
            'current_step': current_step,
            'completed_steps': completed_step_numbers,
            'step_data': {},  # Podemos expandir esto si necesitamos datos específicos
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
        """
        user_email = request.user.email
        
        try:
            # Verificar si ya tiene empresa creada
            from apps.companies.models import Company
            existing_companies = Company.objects.filter(
                taxpayer_sii_credentials__user__email=user_email
            )
            
            if existing_companies.exists():
                return Response({
                    'status': 'success',
                    'message': 'Usuario ya tiene empresa creada',
                    'company_id': existing_companies.first().id,
                    'company_name': existing_companies.first().business_name
                })
            
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
            
            # Verificar si ya se creó la empresa desde el paso
            if company_step_data.step_data.get('company_creation_result'):
                creation_result = company_step_data.step_data['company_creation_result']
                if creation_result.get('status') == 'success':
                    return Response({
                        'status': 'success',
                        'message': 'Empresa ya fue creada durante el onboarding',
                        'creation_result': creation_result
                    })
            
            # Crear empresa si no existe
            company_result = self._create_company_from_onboarding(request, company_step_data.step_data)
            
            if company_result.get('error'):
                return Response(company_result, status=status.HTTP_400_BAD_REQUEST)
            
            # Actualizar step_data con resultado
            company_step_data.step_data['company_creation_result'] = company_result
            company_step_data.save()
            
            # Marcar onboarding como completado
            self.complete(request)
            
            return Response({
                'status': 'success',
                'message': 'Onboarding finalizado exitosamente.',
                'company_result': company_result,
                'finalized_at': timezone.now()
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
                
                # INTEGRACIÓN ESPECIAL: Si es el paso de empresa, crear empresa con SII
                if step.name == 'company' and step_data:
                    company_result = self._create_company_from_onboarding(request, step_data)
                    if company_result.get('error'):
                        # Si la empresa ya existe, es OK - no es un error bloqueante
                        if company_result.get('error') == 'COMPANY_EXISTS':
                            step_data['company_creation_result'] = {
                                'status': 'exists',
                                'message': 'Empresa ya existe, continuando con onboarding',
                                'existing_company': True
                            }
                        else:
                            return Response(company_result, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        # Agregar resultado a step_data para guardarlo
                        step_data['company_creation_result'] = company_result
                    
            if step_data:
                user_onboarding.step_data.update(step_data)
            user_onboarding.save()
            
            return Response(UserOnboardingSerializer(user_onboarding).data)
            
        except OnboardingStep.DoesNotExist:
            return Response(
                {'error': 'Invalid step number'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _create_company_from_onboarding(self, request, step_data):
        """
        Crea la empresa con credenciales SII desde datos del onboarding
        """
        try:
            # Validar datos requeridos
            required_fields = ['business_name', 'tax_id', 'password', 'email']
            missing_fields = [field for field in required_fields if not step_data.get(field)]
            
            if missing_fields:
                return {
                    'error': 'MISSING_REQUIRED_FIELDS',
                    'message': f'Campos requeridos faltantes: {", ".join(missing_fields)}',
                    'missing_fields': missing_fields
                }
            
            # Importar modelos necesarios
            from apps.companies.models import Company
            from apps.taxpayers.models import TaxPayer, TaxpayerSiiCredentials
            from apps.sii.api.servicev2 import SIIServiceV2
            
            tax_id = step_data['tax_id']
            password = step_data['password']
            business_name = step_data['business_name']
            email = step_data['email']
            mobile_phone = step_data.get('mobile_phone', '')
            
            # Verificar si la compañía ya existe
            if Company.objects.filter(tax_id=tax_id).exists():
                return {
                    'error': 'COMPANY_EXISTS',
                    'message': f'Ya existe una compañía registrada con el RUT {tax_id}'
                }
            
            # Crear servicio SII y obtener datos del contribuyente
            sii_service = SIIServiceV2.crear_con_password(
                tax_id=tax_id,
                password=password,
                validar_cookies=True,
                auto_relogin=True
            )
            
            # Consultar datos del contribuyente
            response = sii_service.consultar_contribuyente()
            
            if response.get('status') != 'success':
                return {
                    'error': 'SII_ERROR',
                    'message': f'Error obteniendo datos del SII: {response.get("message", "Error desconocido")}'
                }
            
            # Extraer datos del contribuyente
            datos_sii = response.get('datos_contribuyente', {})
            contribuyente_data = datos_sii.get('contribuyente', {})
            
            # Crear la Company primero
            company_data = {
                'tax_id': tax_id,
                'business_name': business_name,
                'display_name': business_name,  # Temporal, se actualizará
                'email': contribuyente_data.get('eMail', email).strip() if contribuyente_data.get('eMail') else email,
                'mobile_phone': contribuyente_data.get('telefonoMovil', mobile_phone).strip() if contribuyente_data.get('telefonoMovil') else mobile_phone,
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
            
            # Crear TaxPayer con datos del SII, vinculado a la company
            rut, dv = tax_id.split('-')
            taxpayer = TaxPayer.objects.create(
                company=company,
                rut=rut,
                dv=dv.upper(),
                tax_id=tax_id
            )
            
            # Sincronizar con los datos del SII - pasar todos los datos, no solo contribuyente
            taxpayer.sync_from_sii_data(datos_sii)
            taxpayer.save()
            
            # Sincronizar modelos relacionados que necesitan la company
            taxpayer._sync_address_from_sii(datos_sii, company=company)
            taxpayer._sync_activity_from_sii(datos_sii, company=company)
            
            # Sincronizar algunos datos de la company desde taxpayer
            company.sync_taxpayer_data()
            company.save()
            
            # Almacenar credenciales encriptadas
            credentials = TaxpayerSiiCredentials.objects.create(
                company=company,
                user=request.user,
                tax_id=tax_id
            )
            credentials.set_password(password)
            credentials.save()
            
            # Disparar sincronización inicial de DTEs inmediatamente después de crear la empresa
            dte_sync_result = self._start_initial_dte_sync(company.id)
            
            return {
                'status': 'success',
                'message': 'Empresa creada exitosamente desde onboarding y sincronización de DTEs iniciada',
                'company_data': {
                    'company_id': company.id,
                    'tax_id': company.tax_id,
                    'business_name': company.business_name,
                    'display_name': company.display_name,
                    'razon_social': taxpayer.razon_social,
                    'credentials_stored': True
                },
                'dte_sync_result': dte_sync_result
            }
                
        except Exception as e:
            import traceback
            return {
                'error': 'COMPANY_CREATION_ERROR',
                'message': f'Error interno: {str(e)}',
                'traceback': traceback.format_exc()
            }

    def _start_initial_dte_sync(self, company_id):
        """
        Inicia la sincronización de DTEs del mes anterior para la nueva empresa
        """
        try:
            from datetime import datetime, date, timedelta
            from apps.companies.models import Company
            
            # Obtener la empresa
            company = Company.objects.get(id=company_id)
            
            # Calcular fecha del mes anterior
            today = date.today()
            first_day_current_month = today.replace(day=1)
            last_day_previous_month = first_day_current_month - timedelta(days=1)
            first_day_previous_month = last_day_previous_month.replace(day=1)
            
            fecha_desde = first_day_previous_month.strftime('%Y-%m-%d')
            fecha_hasta = last_day_previous_month.strftime('%Y-%m-%d')
            
            # Importar la tarea de Celery para sincronización SII
            from apps.sii.tasks import sync_sii_documents_task
            
            # Enviar tarea a Celery para procesamiento asíncrono
            rut_parts = company.tax_id.split('-')
            task_result = sync_sii_documents_task.delay(
                company_rut=rut_parts[0],  # RUT sin guión
                company_dv=rut_parts[1] if len(rut_parts) > 1 else 'K',  # DV
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                user_email=getattr(self.request.user, 'email', 'system@fizko.com'),
                priority='high',  # Alta prioridad por ser onboarding
                description=f'Sincronización inicial onboarding - {company.business_name}'
            )
            
            return {
                'status': 'success',
                'message': f'Sincronización de DTEs iniciada para período {fecha_desde} a {fecha_hasta}',
                'task_id': task_result.id,
                'company_id': company_id,
                'sync_period': {
                    'fecha_desde': fecha_desde,
                    'fecha_hasta': fecha_hasta,
                    'period_description': f'Mes anterior ({first_day_previous_month.strftime("%B %Y")})'
                },
                'estimated_completion': '3-5 minutos'
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
        """
        user_email = request.user.email
        
        # Obtener pasos activos requeridos
        required_steps = OnboardingStep.objects.filter(
            is_active=True, 
            is_required=True
        ).count()
        
        # Obtener pasos completados requeridos
        completed_required_steps = UserOnboarding.objects.filter(
            user_email=user_email,
            step__is_active=True,
            step__is_required=True,
            status='completed'
        ).count()
        
        needs_onboarding = completed_required_steps < required_steps
        
        # Debug info para troubleshooting
        missing_steps = []
        if needs_onboarding:
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
            'required_steps': required_steps,
            'completed_required_steps': completed_required_steps,
            'missing_steps': missing_steps
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
        test_user, created = User.objects.get_or_create(
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