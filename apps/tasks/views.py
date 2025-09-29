from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.auth import get_user_model

from .models import (
    Task, TaskCategory, TaskComment, TaskAttachment, TaskLog,
    Process, ProcessTemplate, ProcessTask, ProcessExecution
)
from .serializers import (
    TaskSerializer, TaskCategorySerializer, TaskCommentSerializer,
    TaskAttachmentSerializer, TaskLogSerializer, CreateTaskSerializer,
    ProcessSerializer, ProcessTemplateSerializer, ProcessTaskSerializer,
    ProcessExecutionSerializer, CreateProcessSerializer, ProcessSummarySerializer
)
from apps.core.permissions import IsCompanyMember

User = get_user_model()


class TaskCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet para categorías de tareas"""
    
    queryset = TaskCategory.objects.filter(is_active=True)
    serializer_class = TaskCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class TaskViewSet(viewsets.ModelViewSet):
    """ViewSet para tareas del sistema"""
    
    serializer_class = TaskSerializer
    permission_classes = [permissions.AllowAny]  # Temporal para testing
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'task_type', 'category', 'assigned_to']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority', 'progress_percentage']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filtrar tareas por usuario asignado o creado por el usuario"""
        # Manejar usuario anónimo
        if hasattr(self.request.user, 'email') and self.request.user.email:
            user_email = self.request.user.email
            return Task.objects.filter(
                Q(assigned_to=user_email) | Q(created_by=user_email)
            )
        else:
            # Para usuarios anónimos, devolver todas las tareas (temporal para testing)
            return Task.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateTaskSerializer
        return TaskSerializer
    
    def perform_create(self, serializer):
        """Establecer usuario creador al crear tarea"""
        # Manejar usuario anónimo para creación desde onboarding
        created_by = getattr(self.request.user, 'email', 'anonymous') if hasattr(self.request.user, 'email') else 'anonymous'
        serializer.save(created_by=created_by)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Iniciar una tarea"""
        task = self.get_object()
        if task.status != 'pending':
            return Response(
                {'error': 'Solo se pueden iniciar tareas pendientes'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.start_task()
        return Response({'status': 'task_started', 'started_at': task.started_at})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Completar una tarea"""
        task = self.get_object()
        if task.status not in ['pending', 'in_progress']:
            return Response(
                {'error': 'Solo se pueden completar tareas pendientes o en progreso'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result_data = request.data.get('result_data')
        task.complete_task(result_data)
        return Response({'status': 'task_completed', 'completed_at': task.completed_at})
    
    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        """Marcar una tarea como fallida"""
        task = self.get_object()
        if task.status not in ['pending', 'in_progress']:
            return Response(
                {'error': 'Solo se pueden fallar tareas pendientes o en progreso'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        error_message = request.data.get('error_message', '')
        task.fail_task(error_message)
        return Response({'status': 'task_failed', 'error_message': task.error_message})
    
    @action(detail=True, methods=['patch'])
    def update_progress(self, request, pk=None):
        """Actualizar progreso de una tarea"""
        task = self.get_object()
        progress = request.data.get('progress_percentage')
        
        if progress is None or not (0 <= progress <= 100):
            return Response(
                {'error': 'El progreso debe ser un número entre 0 y 100'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.progress_percentage = progress
        task.save()
        
        return Response({'progress_percentage': task.progress_percentage})
    
    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """Obtener tareas del usuario actual"""
        user_email = request.user.email
        tasks = Task.objects.filter(assigned_to=user_email)
        
        # Estadísticas
        stats = {
            'total': tasks.count(),
            'pending': tasks.filter(status='pending').count(),
            'in_progress': tasks.filter(status='in_progress').count(),
            'completed': tasks.filter(status='completed').count(),
            'failed': tasks.filter(status='failed').count(),
            'overdue': sum(1 for task in tasks if task.is_overdue),
        }
        
        # Tareas recientes (últimas 10)
        recent_tasks = tasks.order_by('-created_at')[:10]
        
        return Response({
            'stats': stats,
            'recent_tasks': TaskSerializer(recent_tasks, many=True).data
        })
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Dashboard de tareas con estadísticas generales"""
        user_email = request.user.email
        all_tasks = Task.objects.filter(
            Q(assigned_to=user_email) | Q(created_by=user_email)
        )
        
        # Estadísticas por estado
        stats_by_status = dict(
            all_tasks.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )
        
        # Estadísticas por prioridad
        stats_by_priority = dict(
            all_tasks.values('priority').annotate(count=Count('id')).values_list('priority', 'count')
        )
        
        # Tareas vencidas
        overdue_tasks = [task for task in all_tasks if task.is_overdue]
        
        # Próximas tareas (próximas 7 días)
        from datetime import timedelta
        next_week = timezone.now() + timedelta(days=7)
        upcoming_tasks = all_tasks.filter(
            due_date__isnull=False,
            due_date__lte=next_week,
            status__in=['pending', 'in_progress']
        ).order_by('due_date')[:5]
        
        return Response({
            'total_tasks': all_tasks.count(),
            'stats_by_status': stats_by_status,
            'stats_by_priority': stats_by_priority,
            'overdue_count': len(overdue_tasks),
            'overdue_tasks': TaskSerializer(overdue_tasks[:5], many=True).data,
            'upcoming_tasks': TaskSerializer(upcoming_tasks, many=True).data,
        })


class TaskCommentViewSet(viewsets.ModelViewSet):
    """ViewSet para comentarios de tareas"""
    
    serializer_class = TaskCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['task', 'is_internal']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filtrar comentarios de tareas del usuario"""
        user_email = self.request.user.email
        return TaskComment.objects.filter(
            Q(task__assigned_to=user_email) | Q(task__created_by=user_email)
        )
    
    def perform_create(self, serializer):
        """Establecer usuario del comentario"""
        serializer.save(user_email=self.request.user.email)


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    """ViewSet para archivos adjuntos de tareas"""
    
    serializer_class = TaskAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['task']
    
    def get_queryset(self):
        """Filtrar adjuntos de tareas del usuario"""
        user_email = self.request.user.email
        return TaskAttachment.objects.filter(
            Q(task__assigned_to=user_email) | Q(task__created_by=user_email)
        )
    
    def perform_create(self, serializer):
        """Establecer usuario que subió el archivo"""
        serializer.save(uploaded_by=self.request.user.email)


class TaskLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para logs de tareas (solo lectura)"""
    
    serializer_class = TaskLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['task', 'level']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filtrar logs de tareas del usuario"""
        user_email = self.request.user.email
        return TaskLog.objects.filter(
            Q(task__assigned_to=user_email) | Q(task__created_by=user_email)
        )


# ViewSets para Procesos

class ProcessTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet para plantillas de procesos"""

    queryset = ProcessTemplate.objects.filter(is_active=True)
    serializer_class = ProcessTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['process_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def perform_create(self, serializer):
        """Establecer usuario creador al crear plantilla"""
        serializer.save(created_by=self.request.user.email)


class ProcessViewSet(viewsets.ModelViewSet):
    """ViewSet para procesos del sistema"""

    serializer_class = ProcessSerializer
    permission_classes = [permissions.AllowAny]  # Temporal para testing - TODO: IsAuthenticated
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'process_type', 'company', 'company_rut', 'assigned_to', 'is_template']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'due_date', 'start_date']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filtrar procesos por usuario y empresa(s)"""
        queryset = Process.objects.all()

        # Filtrar por company_ids (múltiples) o company_id (único)
        company_ids_param = self.request.query_params.get('company_ids')
        company_id = self.request.query_params.get('company_id')

        companies_to_filter = []

        if company_ids_param:
            try:
                # Parsear array de IDs: "1,2,3" -> [1, 2, 3]
                company_ids = [int(id.strip()) for id in company_ids_param.split(',') if id.strip()]
                if company_ids:
                    companies_to_filter = company_ids
            except (ValueError, TypeError):
                # Si los company_ids no son válidos, devolver queryset vacío
                queryset = queryset.none()
                return queryset
        elif company_id:
            try:
                companies_to_filter = [int(company_id)]
            except (ValueError, TypeError):
                # Si el company_id no es válido, devolver queryset vacío
                queryset = queryset.none()
                return queryset

        # Aplicar filtro por empresa(s) si se proporcionaron
        if companies_to_filter:
            queryset = queryset.filter(company_id__in=companies_to_filter)

        # Verificar que el usuario tenga acceso a TODAS las empresas solicitadas
        # Solo aplicar si el usuario está autenticado y tenemos empresas
        if (hasattr(self.request.user, 'email') and
            self.request.user.email and
            self.request.user.is_authenticated and
            companies_to_filter):

            from apps.accounts.models import UserRole

            # Verificar que el usuario tenga un rol activo en TODAS las empresas solicitadas
            user_companies = set(
                UserRole.objects.filter(
                    user__email=self.request.user.email,
                    active=True
                ).values_list('company_id', flat=True)
            )

            requested_companies = set(companies_to_filter)
            if not requested_companies.issubset(user_companies):
                # Si el usuario no tiene acceso a alguna empresa, devolver queryset vacío
                queryset = queryset.none()

        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateProcessSerializer
        elif self.action == 'list':
            return ProcessSummarySerializer
        return ProcessSerializer

    def perform_create(self, serializer):
        """Establecer usuario creador al crear proceso"""
        created_by = getattr(self.request.user, 'email', 'anonymous') if hasattr(self.request.user, 'email') else 'anonymous'
        serializer.save(created_by=created_by)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Iniciar un proceso"""
        process = self.get_object()
        if process.status != 'draft':
            return Response(
                {'error': 'Solo se pueden iniciar procesos en borrador'},
                status=status.HTTP_400_BAD_REQUEST
            )

        process.start_process()

        # Crear ejecución
        execution = ProcessExecution.objects.create(
            process=process,
            total_steps=process.process_tasks.count()
        )

        return Response({
            'status': 'process_started',
            'started_at': process.start_date,
            'execution_id': execution.id
        })

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Completar un proceso"""
        process = self.get_object()
        if process.status not in ['active', 'paused']:
            return Response(
                {'error': 'Solo se pueden completar procesos activos o pausados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        process.complete_process()

        # Actualizar ejecución activa
        active_execution = process.executions.filter(status='running').first()
        if active_execution:
            active_execution.status = 'completed'
            active_execution.completed_at = timezone.now()
            active_execution.save()

        return Response({
            'status': 'process_completed',
            'completed_at': process.completed_at
        })

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pausar un proceso"""
        process = self.get_object()
        if process.status != 'active':
            return Response(
                {'error': 'Solo se pueden pausar procesos activos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        process.status = 'paused'
        process.save()

        return Response({'status': 'process_paused'})

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Reanudar un proceso pausado"""
        process = self.get_object()
        if process.status != 'paused':
            return Response(
                {'error': 'Solo se pueden reanudar procesos pausados'},
                status=status.HTTP_400_BAD_REQUEST
            )

        process.status = 'active'
        process.save()

        return Response({'status': 'process_resumed'})

    @action(detail=True, methods=['post'])
    def add_task(self, request, pk=None):
        """Agregar una tarea al proceso"""
        process = self.get_object()
        task_id = request.data.get('task_id')
        execution_order = request.data.get('execution_order', 0)

        if not task_id:
            return Response(
                {'error': 'Se requiere task_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            task = Task.objects.get(id=task_id)
            process_task, created = ProcessTask.objects.get_or_create(
                process=process,
                task=task,
                defaults={
                    'execution_order': execution_order,
                    'is_optional': request.data.get('is_optional', False),
                    'can_run_parallel': request.data.get('can_run_parallel', False),
                }
            )

            if created:
                return Response({
                    'message': 'Tarea agregada al proceso',
                    'process_task_id': process_task.id
                })
            else:
                return Response(
                    {'error': 'La tarea ya está en el proceso'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Task.DoesNotExist:
            return Response(
                {'error': 'Tarea no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Dashboard de procesos con estadísticas"""
        user_email = request.user.email if hasattr(request.user, 'email') else 'anonymous'
        all_processes = Process.objects.filter(
            Q(assigned_to=user_email) | Q(created_by=user_email)
        )

        # Estadísticas por estado
        stats_by_status = dict(
            all_processes.values('status').annotate(count=Count('id')).values_list('status', 'count')
        )

        # Estadísticas por tipo
        stats_by_type = dict(
            all_processes.values('process_type').annotate(count=Count('id')).values_list('process_type', 'count')
        )

        # Procesos vencidos
        overdue_processes = [p for p in all_processes if p.is_overdue]

        # Próximos procesos (próximos 7 días)
        from datetime import timedelta
        next_week = timezone.now() + timedelta(days=7)
        upcoming_processes = all_processes.filter(
            due_date__isnull=False,
            due_date__lte=next_week,
            status__in=['draft', 'active', 'paused']
        ).order_by('due_date')[:5]

        return Response({
            'total_processes': all_processes.count(),
            'stats_by_status': stats_by_status,
            'stats_by_type': stats_by_type,
            'overdue_count': len(overdue_processes),
            'overdue_processes': ProcessSummarySerializer(overdue_processes[:5], many=True).data,
            'upcoming_processes': ProcessSummarySerializer(upcoming_processes, many=True).data,
        })


class ProcessTaskViewSet(viewsets.ModelViewSet):
    """ViewSet para tareas de procesos"""

    serializer_class = ProcessTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['process', 'is_optional', 'can_run_parallel']
    ordering = ['execution_order']

    def get_queryset(self):
        """Filtrar tareas de procesos del usuario"""
        user_email = self.request.user.email
        return ProcessTask.objects.filter(
            Q(process__assigned_to=user_email) | Q(process__created_by=user_email)
        )


class ProcessExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para ejecuciones de procesos (solo lectura)"""

    serializer_class = ProcessExecutionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['process', 'status']
    ordering = ['-started_at']

    def get_queryset(self):
        """Filtrar ejecuciones de procesos del usuario"""
        user_email = self.request.user.email
        return ProcessExecution.objects.filter(
            Q(process__assigned_to=user_email) | Q(process__created_by=user_email)
        )