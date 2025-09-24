from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from datetime import datetime
from django.utils import timezone
import logging

from .models import Company
from .serializers import CompanySerializer, CompanyCreateSerializer, CompanyWithSiiDataSerializer
from apps.sii.api.servicev2 import SIIServiceV2
from apps.sii.utils.exceptions import SIIServiceException, SIIAuthenticationError
from apps.core.permissions import CanOnlyAccessOwnCompanies

logger = logging.getLogger(__name__)


class CompanyViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de compañías"""
    queryset = Company.objects.all()
    permission_classes = [IsAuthenticated, CanOnlyAccessOwnCompanies]  # ✅ PERMISOS ESTRICTOS
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        return CompanySerializer
    
    def get_queryset(self):
        """Filtrar compañías solo del usuario autenticado"""
        # ✅ SOLO EMPRESAS DEL USUARIO ACTUAL
        user = self.request.user
        from apps.accounts.models import UserRole
        
        # Obtener solo las empresas donde el usuario tiene algún rol activo
        user_company_ids = UserRole.objects.filter(
            user=user,
            active=True
        ).values_list('company_id', flat=True)
        
        return Company.objects.filter(
            id__in=user_company_ids,
            is_active=True
        ).select_related('taxpayer')
    
    def perform_create(self, serializer):
        """Al crear una empresa, asociarla con el usuario actual como owner"""
        company = serializer.save()
        
        # Crear rol de owner para el usuario que crea la empresa
        from apps.accounts.models import Role, UserRole
        
        # Obtener o crear el rol de owner
        owner_role, _ = Role.objects.get_or_create(
            name='owner',
            defaults={
                'description': 'Propietario de la empresa con todos los permisos',
                'permissions': {
                    'companies': ['create', 'read', 'update', 'delete'],
                    'documents': ['create', 'read', 'update', 'delete', 'export'],
                    'forms': ['create', 'read', 'update', 'delete'],
                    'expenses': ['create', 'read', 'update', 'delete'],
                    'analytics': ['read', 'export'],
                    'settings': ['read', 'update'],
                    'users': ['create', 'read', 'update', 'delete']
                }
            }
        )
        
        # Asignar rol de owner al usuario actual
        UserRole.objects.get_or_create(
            user=self.request.user,
            company=company,
            role=owner_role,
            defaults={'active': True}
        )
        
        logger.info(f"✅ Usuario {self.request.user.email} creó empresa {company.name} y se asignó como owner")
    
    @action(detail=True, methods=['get'])
    def sii_status(self, request, pk=None):
        """Obtener estado de integración SII de una empresa"""
        company = self.get_object()
        
        # Temporalmente simular estado SII sin verificar usuario
        # Verificar si tiene credenciales SII (sin filtro de usuario)
        sii_credentials = company.taxpayer_sii_credentials.filter(
            is_active=True
        ).first()
        
        if not sii_credentials:
            return Response({
                'integrated': False,
                'credentials_valid': False,
                'message': 'No hay credenciales SII configuradas'
            })
        
        # Verificar validez de credenciales (simulado por ahora)
        return Response({
            'integrated': True,
            'credentials_valid': True,
            'last_sync': sii_credentials.updated_at.isoformat() if hasattr(sii_credentials, 'updated_at') else None,
            'sync_status': 'active'
        })
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """Obtener métricas básicas de la empresa"""
        company = self.get_object()

        # Por ahora devolvemos datos mock hasta implementar documentos
        return Response({
            'total_documents': 0,
            'total_sales': 0,
            'total_purchases': 0,
            'pending_documents': 0,
            'last_update': timezone.now().isoformat()
        })

    @action(detail=True, methods=['get'])
    def process_settings(self, request, pk=None):
        """Obtener configuración de procesos tributarios de la empresa"""
        company = self.get_object()

        if not hasattr(company, 'taxpayer'):
            return Response({
                'error': 'NO_TAXPAYER',
                'message': 'Esta empresa no tiene TaxPayer configurado'
            }, status=status.HTTP_404_NOT_FOUND)

        taxpayer = company.taxpayer
        settings = taxpayer.get_process_settings()

        # Obtener procesos activos
        from apps.tasks.models import Process
        active_processes = Process.objects.filter(
            company_rut=taxpayer.rut,
            status__in=['active', 'in_progress', 'scheduled']
        ).values('process_type', 'name', 'status', 'due_date')

        return Response({
            'company_id': company.id,
            'company_name': company.display_name,
            'taxpayer_rut': taxpayer.tax_id,
            'settings': settings,
            'active_processes': list(active_processes),
            'available_processes': {
                'f29_monthly': 'F29 - Declaración Mensual IVA',
                'f22_annual': 'F22 - Declaración Anual Renta',
                'f3323_quarterly': 'F3323 - Declaración Trimestral ProPyme'
            }
        })

    @action(detail=True, methods=['post'])
    def update_process_settings(self, request, pk=None):
        """Actualizar configuración de procesos y crear/eliminar procesos según corresponda"""
        company = self.get_object()

        if not hasattr(company, 'taxpayer'):
            return Response({
                'error': 'NO_TAXPAYER',
                'message': 'Esta empresa no tiene TaxPayer configurado'
            }, status=status.HTTP_404_NOT_FOUND)

        taxpayer = company.taxpayer
        new_settings = request.data.get('settings', {})

        if not isinstance(new_settings, dict):
            return Response({
                'error': 'INVALID_SETTINGS',
                'message': 'settings debe ser un objeto con los procesos a habilitar/deshabilitar'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Obtener configuración actual y comparar
        current_settings = taxpayer.get_process_settings()
        changes = {
            'enabled': [],
            'disabled': [],
            'unchanged': []
        }

        # Identificar cambios
        for process_type in ['f29_monthly', 'f22_annual', 'f3323_quarterly']:
            if process_type in new_settings:
                new_value = bool(new_settings[process_type])
                current_value = current_settings.get(process_type, False)

                if new_value and not current_value:
                    changes['enabled'].append(process_type)
                elif not new_value and current_value:
                    changes['disabled'].append(process_type)
                else:
                    changes['unchanged'].append(process_type)

        # Actualizar configuración
        taxpayer.update_process_settings(new_settings)

        # Procesar cambios
        results = {
            'enabled_processes': [],
            'disabled_processes': [],
            'errors': []
        }

        with transaction.atomic():
            # Habilitar nuevos procesos
            if changes['enabled']:
                from apps.tasks.tasks.process_management import create_processes_from_taxpayer_settings

                try:
                    # Ejecutar creación de procesos síncronamente
                    creation_result = create_processes_from_taxpayer_settings(company_id=company.id)

                    if creation_result.get('processes_created'):
                        for process in creation_result['processes_created']:
                            results['enabled_processes'].append({
                                'type': process['type'],
                                'name': process['name'],
                                'id': process['process_id']
                            })

                    if creation_result.get('errors'):
                        results['errors'].extend(creation_result['errors'])

                except Exception as e:
                    logger.error(f"Error creando procesos para empresa {company.id}: {str(e)}")
                    results['errors'].append(f"Error creando procesos: {str(e)}")

            # Deshabilitar procesos existentes
            if changes['disabled']:
                from apps.tasks.models import Process, ProcessTask

                for process_type in changes['disabled']:
                    # Mapear tipo de configuración a tipo de proceso
                    process_type_map = {
                        'f29_monthly': 'f29',
                        'f22_annual': 'f22',
                        'f3323_quarterly': 'f3323'
                    }

                    actual_process_type = process_type_map.get(process_type, process_type.split('_')[0])

                    # Cancelar procesos activos de este tipo
                    processes_to_cancel = Process.objects.filter(
                        company_rut=taxpayer.rut,
                        process_type=actual_process_type,
                        status__in=['active', 'scheduled', 'draft']
                    )

                    for process in processes_to_cancel:
                        # Cancelar todas las tareas del proceso
                        ProcessTask.objects.filter(process=process).update(
                            status='cancelled'
                        )

                        # Cancelar el proceso
                        process.status = 'cancelled'
                        process.save()

                        results['disabled_processes'].append({
                            'type': process.process_type,
                            'name': process.name,
                            'id': process.id
                        })

                    logger.info(f"Cancelados {processes_to_cancel.count()} procesos {actual_process_type} para {taxpayer.tax_id}")

        return Response({
            'status': 'success',
            'company_id': company.id,
            'changes': changes,
            'results': results,
            'new_settings': taxpayer.get_process_settings()
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_company_with_sii_data(request):
    """
    Endpoint integrado que:
    1. Verifica credenciales SII
    2. Crea la compañía
    3. Obtiene información completa del contribuyente
    
    POST /api/v1/companies/create-with-sii/
    {
        "business_name": "Mi Empresa",
        "tax_id": "77794858-k",
        "password": "SiiPfufl574@#",
        "email": "contacto@miempresa.cl",
        "mobile_phone": "+56912345678"
    }
    """
    try:
        # Validar datos de entrada
        serializer = CompanyWithSiiDataSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "error": "VALIDATION_ERROR",
                "message": "Datos inválidos",
                "details": serializer.errors,
                "timestamp": timezone.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        tax_id = validated_data['tax_id']
        password = validated_data['password']
        business_name = validated_data['business_name']
        email = validated_data['email']
        mobile_phone = validated_data.get('mobile_phone', '')
        
        logger.info(f"🏢 Creando compañía con datos SII: {tax_id}")
        
        # Verificar si la compañía ya existe
        if Company.objects.filter(tax_id=tax_id).exists():
            return Response({
                "error": "COMPANY_EXISTS",
                "message": f"Ya existe una compañía registrada con el RUT {tax_id}",
                "timestamp": timezone.now().isoformat()
            }, status=status.HTTP_409_CONFLICT)
        
        # Paso 1: Verificar credenciales SII usando configuración de ambiente
        logger.info(f"🔍 Paso 1: Verificando credenciales SII para {tax_id}")
        import os
        use_real_service = True  # Forzar servicio real temporalmente
        logger.info(f"🔧 Usando servicio real SII: {use_real_service}")
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            use_real_service=use_real_service
        )
        
        try:
            sii_service.authenticate()
            contribuyente_data = sii_service.get_taxpayer_info()
        finally:
            # Cerrar servicio para liberar recursos
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
        # Paso 2: Crear Company primero, luego TaxPayer vinculado
        logger.info(f"🏗️ Paso 2: Creando Company y TaxPayer para {tax_id}")
        
        # Crear la Company primero con datos básicos
        company_data = {
            'tax_id': tax_id,
            'business_name': business_name,
            'display_name': business_name,  # Temporal, se actualizará
            'email': contribuyente_data.get('email', email).strip() if contribuyente_data.get('email') else email,
            'mobile_phone': contribuyente_data.get('mobile_phone', mobile_phone).strip() if contribuyente_data.get('mobile_phone') else mobile_phone,
            'person_company': 'EMPRESA',  # Por defecto, se actualizará
            'electronic_biller': True,
            'is_active': True,
            'preferred_currency': 'CLP',
            'time_zone': 'America/Santiago',
            'notify_new_documents': True,
            'notify_tax_deadlines': True,
            'notify_system_updates': True
        }
        
        company = Company.objects.create(**company_data)
        logger.info(f"✅ Company creada: {company.business_name} (ID: {company.id})")
        
        # Ahora crear el TaxPayer vinculado a la Company
        rut, dv = tax_id.split('-')
        from apps.taxpayers.models import TaxPayer
        taxpayer = TaxPayer.objects.create(
            company=company,
            rut=rut,
            dv=dv.upper(),
            tax_id=tax_id
        )
        
        # Sincronizar con los datos del SII
        taxpayer.sync_from_sii_data(contribuyente_data)
        taxpayer.save()
        logger.info(f"✅ TaxPayer creado y sincronizado: {taxpayer.razon_social}")
        
        # Sincronizar modelos relacionados que necesitan la company
        taxpayer._sync_address_from_sii(contribuyente_data, company=company)
        taxpayer._sync_activity_from_sii(contribuyente_data, company=company)
        
        # Sincronizar algunos datos de la company desde taxpayer
        company.sync_taxpayer_data()
        company.save()
        
        logger.info(f"✅ Company creada: {company.name} (ID: {company.id})")
        
        # Paso 3: Almacenar credenciales del SII de forma encriptada
        logger.info(f"🔐 Paso 3: Almacenando credenciales del SII de forma encriptada")
        from apps.taxpayers.models import TaxpayerSiiCredentials
        
        credentials = TaxpayerSiiCredentials.objects.create(
            company=company,
            user=request.user,
            tax_id=tax_id
        )
        credentials.set_password(password)
        credentials.save()
        
        logger.info(f"✅ Credenciales almacenadas de forma encriptada para {tax_id}")
        
        # Paso 4: Obtener información completa del contribuyente
        logger.info(f"📊 Paso 4: Información completa obtenida para {tax_id}")
        
        # Preparar respuesta completa
        company_serializer = CompanySerializer(company)
        
        response_data = {
            "status": "success",
            "message": "Compañía creada exitosamente con datos del SII",
            "timestamp": timezone.now().isoformat(),
            "data": {
                "company": company_serializer.data,
                "taxpayer": {
                    "id": taxpayer.id,
                    "tax_id": taxpayer.tax_id,
                    "razon_social": taxpayer.razon_social,
                    "tipo_contribuyente": taxpayer.tipo_contribuyente,
                    "estado": taxpayer.estado,
                    "actividad_description": taxpayer.actividad_description,
                    "fecha_inicio_actividades": str(taxpayer.fecha_inicio_actividades) if taxpayer.fecha_inicio_actividades else None,
                    "direccion": taxpayer.direccion,
                    "comuna": taxpayer.comuna,
                    "region": taxpayer.region,
                    "email": taxpayer.email,
                    "mobile_phone": taxpayer.mobile_phone,
                    "is_verified": taxpayer.is_verified,
                    "last_sii_sync": taxpayer.last_sii_sync.isoformat() if taxpayer.last_sii_sync else None
                },
                "sii_verification": {
                    "tax_id": tax_id,
                    "valid_credentials": True,
                    "company_name": taxpayer.razon_social,
                    "company_type": taxpayer.tipo_contribuyente,
                    "status": taxpayer.estado,
                    "activity_description": taxpayer.actividad_description,
                    "activity_start_date": str(taxpayer.fecha_inicio_actividades) if taxpayer.fecha_inicio_actividades else '',
                    "email": taxpayer.email,
                    "mobile_phone": taxpayer.mobile_phone,
                    "address": taxpayer.direccion,
                    "comuna": taxpayer.comuna,
                    "region": taxpayer.region,
                    "authentication_method": "password",
                    "data_source": taxpayer.data_source,
                    "credentials_stored": True
                },
                "credentials": {
                    "id": credentials.id,
                    "is_active": credentials.is_active,
                    "created_at": credentials.created_at.isoformat(),
                    "user_id": credentials.user.id,
                    "user_username": credentials.user.username if hasattr(credentials.user, 'username') else 'N/A'
                }
            }
        }
        
        logger.info(f"✅ Compañía {company.id} creada exitosamente: {company.name}")
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except SIIAuthenticationError as e:
        logger.error(f"❌ Error de autenticación SII: {str(e)}")
        return Response({
            "error": "SII_AUTH_ERROR",
            "message": "Credenciales del SII inválidas. Verifica tu RUT y contraseña.",
            "timestamp": datetime.now().isoformat(),
            "details": str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except SIIServiceException as e:
        logger.error(f"❌ Error del servicio SII: {str(e)}")
        return Response({
            "error": "SII_SERVICE_ERROR", 
            "message": "Error al conectar con el servicio SII. Intenta más tarde.",
            "timestamp": datetime.now().isoformat(),
            "details": str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except Exception as e:
        logger.error(f"❌ Error interno creando compañía: {str(e)}")
        return Response({
            "error": "INTERNAL_ERROR",
            "message": f"Error interno del servidor: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_sii_credentials(request):
    """
    Actualizar/crear credenciales SII para empresa existente
    
    POST /api/v1/companies/update-sii-credentials/
    {
        "tax_id": "77794858-k",
        "password": "password"
    }
    """
    try:
        # Validar datos de entrada
        tax_id = request.data.get('tax_id')
        password = request.data.get('password')
        
        if not tax_id or not password:
            return Response({
                "error": "VALIDATION_ERROR",
                "message": "tax_id y password son requeridos",
                "timestamp": timezone.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Normalizar tax_id
        tax_id = tax_id.upper().strip()
        logger.info(f"🔄 Actualizando credenciales SII para {tax_id}")
        
        # Buscar empresa por tax_id (case insensitive)
        try:
            company = Company.objects.get(tax_id__iexact=tax_id, is_active=True)
        except Company.DoesNotExist:
            logger.warning(f"❌ Empresa no encontrada para tax_id: {tax_id}")
            return Response({
                "error": "COMPANY_NOT_FOUND", 
                "message": f"No se encontró empresa activa con RUT {tax_id}",
                "timestamp": timezone.now().isoformat()
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verificar credenciales SII antes de actualizar
        logger.info(f"🔐 Verificando nuevas credenciales SII para {tax_id}")
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        # Create service and verify credentials
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            use_real_service=True
        )
        
        try:
            sii_service.authenticate()
            verification_result = {'status': 'success'}
        except Exception as e:
            verification_result = {'status': 'error', 'message': str(e)}
        finally:
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
        if verification_result.get('status') != 'success':
            logger.warning(f"❌ Credenciales inválidas para {tax_id}")
            return Response({
                "error": "INVALID_CREDENTIALS",
                "message": "Las credenciales SII proporcionadas no son válidas",
                "timestamp": timezone.now().isoformat()
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Actualizar o crear credenciales
        from apps.taxpayers.models import TaxpayerSiiCredentials
        
        credentials, created = TaxpayerSiiCredentials.objects.update_or_create(
            company=company,
            user=request.user,
            defaults={
                'tax_id': tax_id,
                'encrypted_password': password,  # El modelo se encarga del cifrado
                'is_active': True,
                'last_verified': timezone.now()
            }
        )
        
        action_text = "creadas" if created else "actualizadas"
        logger.info(f"✅ Credenciales SII {action_text} para {tax_id}")
        
        return Response({
            "status": "success",
            "message": f"Credenciales SII {action_text} exitosamente para {company.business_name}",
            "timestamp": timezone.now().isoformat(),
            "data": {
                "company_id": company.id,
                "tax_id": company.tax_id,
                "company_name": company.business_name,
                "credentials_action": "created" if created else "updated",
                "last_verified": credentials.last_verified.isoformat() if credentials.last_verified else None
            }
        }, status=status.HTTP_200_OK)
        
    except SIIAuthenticationError as e:
        logger.error(f"❌ Error de autenticación SII: {str(e)}")
        return Response({
            "error": "SII_AUTH_ERROR",
            "message": "Error de autenticación con el SII. Verifica las credenciales.",
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except SIIServiceException as e:
        logger.error(f"❌ Error de servicio SII: {str(e)}")
        return Response({
            "error": "SII_SERVICE_ERROR",
            "message": "El servicio del SII no está disponible temporalmente",
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except Exception as e:
        logger.error(f"❌ Error interno actualizando credenciales: {str(e)}")
        return Response({
            "error": "INTERNAL_ERROR",
            "message": f"Error interno del servidor: {str(e)}",
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([])
def test_company_creation(request):
    """
    Vista de prueba temporal para verificar creación de compañía con datos completos del SII
    """
    try:
        # SII service import moved to top
        
        # Obtener datos del contribuyente
        tax_id = "77794858-k"
        password = "SiiPfufl574@#"
        
        logger.info(f"🧪 Iniciando prueba de creación de compañía con {tax_id}")
        
        # Limpiar compañía existente
        Company.objects.filter(tax_id=tax_id).delete()
        logger.info("🧹 Compañía anterior eliminada")
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        # Crear servicio SII y obtener datos
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            use_real_service=True
        )
        
        try:
            sii_service.authenticate()
            contribuyente_data = sii_service.get_taxpayer_info()
            logger.info(f"📊 Datos obtenidos del SII: {contribuyente_data.get('razon_social')}")
        finally:
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
        # Crear TaxPayer y Company usando los nuevos modelos
        rut, dv = tax_id.split('-')
        
        # Crear el TaxPayer con los datos del SII
        from apps.taxpayers.models import TaxPayer
        taxpayer = TaxPayer.objects.create(
            rut=rut,
            dv=dv.upper(),
            tax_id=tax_id
        )
        
        # Sincronizar con los datos del SII
        taxpayer.sync_from_sii_data(contribuyente_data)
        taxpayer.save()
        
        logger.info(f"✅ TaxPayer creado: {taxpayer.razon_social}")
        
        # Crear la Company con datos de prueba
        company_data = {
            'taxpayer': taxpayer,
            'tax_id': tax_id,
            'business_name': 'Test Business Name',
            'display_name': taxpayer.razon_social,
            'email': contribuyente_data.get('email', 'test@empresa.cl').strip() if contribuyente_data.get('email') else 'test@empresa.cl',
            'mobile_phone': contribuyente_data.get('mobile_phone', '+56912345678').strip() if contribuyente_data.get('mobile_phone') else '+56912345678',
            'person_company': 'EMPRESA',  # TODO: Determinar basado en datos SII
            'electronic_biller': True,
            'is_active': True,
            'preferred_currency': 'CLP',
            'time_zone': 'America/Santiago'
        }
        
        # Crear compañía
        company = Company.objects.create(**company_data)
        company.sync_taxpayer_data()
        company.save()
        
        logger.info(f"🏢 Compañía creada: {company.name} (ID: {company.id})")
        
        # Almacenar credenciales de prueba (crear usuario de prueba si no existe)
        from django.contrib.auth import get_user_model
        from apps.taxpayers.models import TaxpayerSiiCredentials
        
        User = get_user_model()
        test_user, created = User.objects.get_or_create(
            username='test_user',
            defaults={
                'email': 'test@test.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        credentials = TaxpayerSiiCredentials.objects.create(
            company=company,
            user=test_user,
            tax_id=tax_id
        )
        credentials.set_password(password)
        credentials.save()
        
        logger.info(f"✅ Credenciales de prueba almacenadas para {tax_id}")
        
        return Response({
            "status": "success",
            "message": "Compañía creada exitosamente con datos reales del SII",
            "timestamp": timezone.now().isoformat(),
            "data": {
                "company_id": company.id,
                "name": company.name,
                "tax_id": company.tax_id,
                "razon_social": company.razon_social,
                "activity": company.activity_description,
                "email": company.email,
                "phone": company.mobile_phone,
                "address": company.sii_address,
                "activity_start_date": str(company.activity_start_date) if company.activity_start_date else None,
                "person_company": company.person_company,
                "electronic_biller": company.electronic_biller,
                "full_rut": company.full_rut,
                "is_verified_with_sii": company.is_verified_with_sii
            },
            "taxpayer": {
                "id": taxpayer.id,
                "razon_social": taxpayer.razon_social,
                "tipo_contribuyente": taxpayer.tipo_contribuyente,
                "estado": taxpayer.estado,
                "last_sii_sync": taxpayer.last_sii_sync.isoformat() if taxpayer.last_sii_sync else None
            },
            "sii_raw_data": contribuyente_data
        })
        
    except Exception as e:
        logger.error(f"❌ Error en prueba: {str(e)}")
        return Response({
            "error": "TEST_ERROR",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([])
def test_credentials_validation(request):
    """
    Vista de prueba para verificar el manejo de credenciales inválidas
    """
    try:
        # SII service import moved to top
        
        # Obtener datos del request
        data = request.data
        tax_id = data.get('tax_id', '12345678-9')
        password = data.get('password', 'invalid_password')
        
        logger.info(f"🧪 Probando verificación de credenciales: {tax_id}")
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        # Intentar verificar credenciales
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            use_real_service=True
        )
        
        try:
            sii_service.authenticate()
            contribuyente_data = sii_service.get_taxpayer_info()
            result = {
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'data': {
                    'company_name': contribuyente_data.get('razon_social', 'N/A'),
                    'company_type': contribuyente_data.get('tipo_contribuyente', 'N/A')
                }
            }
        except Exception as e:
            result = {
                'status': 'error',
                'timestamp': timezone.now().isoformat(),
                'message': str(e)
            }
        finally:
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
        # Simular respuesta como la API real
        if result['status'] == 'success':
            return Response({
                "status": "success",
                "timestamp": result['timestamp'],
                "tax_id": tax_id,
                "data": {
                    "status": "success",
                    "message": "Credenciales válidas",
                    "datos_contribuyente": {
                        "codigoError": 0,
                        "descripcionError": "",
                        "contribuyente": {
                            "razonSocial": result['data']['company_name'],
                            "rut": tax_id,
                            "dv": tax_id.split('-')[1],
                            "tipoContribuyenteDescripcion": result['data']['company_type']
                        }
                    }
                }
            })
        else:
            return Response({
                "status": "error",
                "timestamp": result['timestamp'],
                "tax_id": tax_id,
                "data": {
                    "status": "error",
                    "message": result['message'] or "Credenciales inválidas"
                }
            })
            
    except Exception as e:
        logger.error(f"❌ Error en prueba de credenciales: {str(e)}")
        return Response({
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "tax_id": tax_id,
            "data": {
                "status": "error",
                "message": f"Error de verificación: {str(e)}"
            }
        })


@api_view(['POST'])  
@permission_classes([])
def test_create_with_sii_no_auth(request):
    """
    Vista de prueba para probar create_company_with_sii_data sin autenticación
    """
    try:
        logger.info("🧪 Testing create-with-sii endpoint without auth")
        
        # Test data
        test_data = {
            "business_name": "Mi Empresa Test",
            "tax_id": "77794858-k", 
            "password": "SiiPfufl574@#",
            "email": "test@miempresa.cl",
            "mobile_phone": "+56912345678"
        }
        
        # Clean up previous company
        Company.objects.filter(tax_id="77794858-k").delete()
        
        # Simulate the main endpoint logic
        serializer = CompanyWithSiiDataSerializer(data=test_data)
        if not serializer.is_valid():
            return Response({
                "error": "VALIDATION_ERROR",
                "message": "Datos inválidos",
                "details": serializer.errors,
                "timestamp": timezone.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        tax_id = validated_data['tax_id']
        password = validated_data['password']
        
        # Test SII integration
        import os
        use_real_service = os.getenv('SII_USE_REAL_SERVICE', 'false').lower() == 'true'
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            use_real_service=use_real_service
        )
        
        try:
            sii_service.authenticate()
            contribuyente_data = sii_service.get_taxpayer_info()
        finally:
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
        return Response({
            "status": "success",
            "message": "SII integration test successful", 
            "timestamp": timezone.now().isoformat(),
            "service_type": "real" if use_real_service else "mock",
            "data": {
                "tax_id": tax_id,
                "sii_data": contribuyente_data
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error in create-with-sii test: {str(e)}")
        return Response({
            "error": "TEST_ERROR",
            "message": str(e),
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])  
@permission_classes([])
def test_force_real_sii(request):
    """
    Vista de prueba para forzar el uso del servicio real SII (sin fallback)
    """
    try:
        logger.info("🧪 Testing FORCED real SII service")
        
        tax_id = "77794858-k"
        password = "SiiPfufl574@#"
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        # Force real service creation
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            use_real_service=True
        )
        
        try:
            # Test authentication
            auth_result = sii_service.authenticate()
            logger.info(f"✅ Real SII authentication result: {auth_result}")
            
            # Get data
            contribuyente_data = sii_service.get_taxpayer_info()
            logger.info(f"✅ Real SII data retrieved: {contribuyente_data.get('razon_social')}")
            
            return Response({
                "status": "success",
                "message": "Real SII service test successful!",
                "timestamp": timezone.now().isoformat(),
                "service_type": "real",
                "auth_result": auth_result,
                "data": {
                    "tax_id": tax_id,
                    "sii_data": contribuyente_data
                }
            })
            
        finally:
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
    except Exception as e:
        logger.error(f"❌ Real SII service error: {str(e)}")
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"Full traceback: {traceback_str}")
        
        return Response({
            "error": "REAL_SII_ERROR",
            "message": str(e),
            "traceback": traceback_str,
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])  
@permission_classes([])
def test_credentials_storage(request):
    """
    Vista de prueba para verificar almacenamiento de credenciales sin conectar al SII
    """
    try:
        from django.contrib.auth import get_user_model
        from apps.taxpayers.models import TaxPayer, TaxpayerSiiCredentials
        from apps.companies.models import Company
        
        User = get_user_model()
        tax_id = "11222333-4"
        
        logger.info(f"🧪 Probando almacenamiento de credenciales para {tax_id}")
        
        # Limpiar datos existentes
        Company.objects.filter(tax_id=tax_id).delete()
        TaxPayer.objects.filter(tax_id=tax_id).delete()
        
        # Crear usuario de prueba
        test_user, created = User.objects.get_or_create(
            username='credentials_test_user',
            defaults={
                'email': 'credtest@test.com',
                'first_name': 'Credentials',
                'last_name': 'Test'
            }
        )
        
        # Crear TaxPayer con datos simulados
        rut, dv = tax_id.split('-')
        taxpayer = TaxPayer.objects.create(
            rut=rut,
            dv=dv.upper(),
            tax_id=tax_id,
            razon_social="EMPRESA PRUEBA CREDENCIALES SPA",
            tipo_contribuyente="PERSONA JURIDICA COMERCIAL",
            estado="ACTIVO"
        )
        taxpayer.save()
        
        # Crear Company
        company = Company.objects.create(
            taxpayer=taxpayer,
            tax_id=tax_id,
            business_name="Empresa Test Credenciales",
            display_name=taxpayer.razon_social,
            email="test@empresa.cl",
            is_active=True
        )
        company.save()
        
        # Crear y almacenar credenciales encriptadas
        test_password = "ContraseñaPrueba123@"
        credentials = TaxpayerSiiCredentials.objects.create(
            company=company,
            user=test_user,
            tax_id=tax_id
        )
        credentials.set_password(test_password)
        credentials.save()
        
        # Verificar que la contraseña se puede desencriptar
        decrypted_password = credentials.get_password()
        password_match = test_password == decrypted_password
        
        logger.info(f"✅ Credenciales almacenadas y verificadas: {password_match}")
        
        return Response({
            "status": "success",
            "message": "Almacenamiento de credenciales probado exitosamente",
            "timestamp": timezone.now().isoformat(),
            "data": {
                "company": {
                    "id": company.id,
                    "tax_id": company.tax_id,
                    "business_name": company.business_name
                },
                "taxpayer": {
                    "id": taxpayer.id,
                    "razon_social": taxpayer.razon_social
                },
                "credentials": {
                    "id": credentials.id,
                    "user_username": test_user.username,
                    "is_active": credentials.is_active,
                    "password_encrypted": bool(credentials.encrypted_password),
                    "password_verification": password_match,
                    "created_at": credentials.created_at.isoformat()
                },
                "test_info": {
                    "original_password_length": len(test_password),
                    "encrypted_password_length": len(credentials.encrypted_password),
                    "encryption_working": password_match
                }
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error probando credenciales: {str(e)}")
        return Response({
            "error": "CREDENTIALS_TEST_ERROR",
            "message": str(e),
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])  
@permission_classes([])
def test_sync_with_stored_credentials(request):
    """
    Vista de prueba para probar sincronización usando credenciales almacenadas
    """
    try:
        # Buscar una empresa que tenga credenciales almacenadas
        from apps.taxpayers.models import TaxpayerSiiCredentials
        
        credentials = TaxpayerSiiCredentials.objects.filter(is_active=True).first()
        if not credentials:
            return Response({
                "error": "NO_CREDENTIALS",
                "message": "No se encontraron credenciales almacenadas para probar"
            }, status=status.HTTP_404_NOT_FOUND)
        
        company = credentials.company
        logger.info(f"🔄 Probando sincronización con credenciales almacenadas para {company.tax_id}")
        
        # Verificar que tiene credenciales
        has_credentials = company.has_sii_credentials()
        logger.info(f"Empresa tiene credenciales válidas: {has_credentials}")
        
        if not has_credentials:
            return Response({
                "error": "INVALID_CREDENTIALS", 
                "message": "Las credenciales almacenadas no son válidas",
                "credentials_info": {
                    "id": credentials.id,
                    "is_active": credentials.is_active,
                    "verification_failures": credentials.verification_failures,
                    "is_credentials_valid": credentials.is_credentials_valid
                }
            })
        
        # Intentar sincronización (esto conectará al SII con credenciales almacenadas)
        try:
            result = company.sync_with_sii()
            
            return Response({
                "status": "success",
                "message": "Sincronización usando credenciales almacenadas exitosa",
                "timestamp": timezone.now().isoformat(),
                "data": {
                    "company": {
                        "id": company.id,
                        "tax_id": company.tax_id,
                        "business_name": company.business_name,
                        "display_name": company.display_name
                    },
                    "credentials": {
                        "id": credentials.id,
                        "last_verified": credentials.last_verified.isoformat() if credentials.last_verified else None,
                        "verification_failures": credentials.verification_failures,
                        "is_valid": credentials.is_credentials_valid
                    },
                    "sync_result": result,
                    "taxpayer": {
                        "razon_social": company.taxpayer.razon_social if company.taxpayer else None,
                        "last_sync": company.taxpayer.last_sii_sync.isoformat() if company.taxpayer and company.taxpayer.last_sii_sync else None
                    }
                }
            })
            
        except ValueError as e:
            logger.error(f"❌ Error en sincronización: {str(e)}")
            return Response({
                "error": "SYNC_ERROR",
                "message": str(e),
                "credentials_info": {
                    "verification_failures": credentials.verification_failures,
                    "is_valid": credentials.is_credentials_valid
                }
            })
        
    except Exception as e:
        logger.error(f"❌ Error probando sincronización: {str(e)}")
        return Response({
            "error": "TEST_SYNC_ERROR",
            "message": str(e),
            "timestamp": timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])  
@permission_classes([])
def test_logout_flow(request):
    """
    Vista de prueba para simular el flujo completo de logout
    """
    try:
        data = request.data
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        logger.info(f"🧪 Probando flujo de logout")
        logger.info(f"Access token presente: {bool(access_token)}")
        logger.info(f"Refresh token presente: {bool(refresh_token)}")
        
        # Simular llamada al endpoint de logout de Django
        import requests
        
        logout_url = "http://localhost:8000/api/v1/auth/users/logout/"
        headers = {}
        payload = {}
        
        if refresh_token:
            payload['refresh'] = refresh_token
            
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
            
        headers['Content-Type'] = 'application/json'
        
        # Intentar logout en el backend
        try:
            response = requests.post(logout_url, json=payload, headers=headers, timeout=10)
            logger.info(f"Logout backend response: {response.status_code}")
            
            if response.status_code == 200:
                backend_success = True
                backend_message = "Logout exitoso en backend"
            else:
                backend_success = False
                backend_message = f"Backend logout falló: {response.status_code} - {response.text[:200]}"
                
        except requests.exceptions.RequestException as e:
            backend_success = False
            backend_message = f"Error conectando con backend: {str(e)}"
            
        logger.info(f"Backend logout result: {backend_success} - {backend_message}")
        
        # Simular limpieza local (esto siempre debe funcionar)
        local_cleanup = {
            "access_token_cleared": True,
            "refresh_token_cleared": True,
            "user_data_cleared": True,
            "localStorage_cleared": True
        }
        
        return Response({
            "status": "success",
            "message": "Prueba de logout completada",
            "backend_logout": {
                "success": backend_success,
                "message": backend_message
            },
            "local_cleanup": local_cleanup,
            "recommendation": "El logout local siempre debe funcionar aunque falle el backend" if not backend_success else "Logout completo exitoso"
        })
        
    except Exception as e:
        logger.error(f"❌ Error en prueba de logout: {str(e)}")
        return Response({
            "error": "TEST_LOGOUT_ERROR",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)