from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Case, When, BooleanField
from django.db import models
from django.shortcuts import get_object_or_404
import logging

from .models import Contact
from .serializers import (
    ContactSerializer,
    ContactCreateSerializer,
    ContactUpdateSerializer,
    ContactListSerializer,
    ContactStatsSerializer
)
from apps.core.permissions import IsCompanyMember
from apps.accounts.models import UserRole

logger = logging.getLogger(__name__)


class ContactFilter(DjangoFilterBackend):
    """Custom filter for contacts"""

    class Meta:
        model = Contact
        fields = {
            'is_client': ['exact'],
            'is_provider': ['exact'],
            'is_active': ['exact'],
            'category': ['exact', 'icontains'],
            'created_at': ['gte', 'lte'],
        }


class ContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para gestión de contactos

    Provides CRUD operations for contacts with proper filtering,
    search, and company-based access control.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'tax_id', 'email', 'phone', 'category']
    ordering_fields = ['name', 'tax_id', 'created_at', 'updated_at']
    ordering = ['-created_at']

    # Filtros personalizados
    filterset_fields = {
        'is_client': ['exact'],
        'is_provider': ['exact'],
        'is_active': ['exact'],
        'category': ['exact', 'icontains'],
        'created_at': ['gte', 'lte', 'exact'],
        'updated_at': ['gte', 'lte', 'exact'],
    }

    def get_queryset(self):
        """
        Filtrar contactos solo de las empresas donde el usuario tiene acceso
        """
        user = self.request.user

        # Obtener IDs de empresas donde el usuario tiene roles activos
        user_company_ids = UserRole.objects.filter(
            user=user,
            active=True
        ).values_list('company_id', flat=True)

        queryset = Contact.objects.filter(
            company_id__in=user_company_ids
        ).select_related('company')

        # Filtros adicionales por query params
        role_filter = self.request.query_params.get('role')
        if role_filter == 'clients':
            queryset = queryset.filter(is_client=True)
        elif role_filter == 'providers':
            queryset = queryset.filter(is_provider=True)
        elif role_filter == 'dual':
            queryset = queryset.filter(is_client=True, is_provider=True)

        # Support both single and multiple company IDs
        company_id = self.request.query_params.get('company_id')
        company_ids_param = self.request.query_params.get('company_ids')

        if company_ids_param:
            # Parse comma-separated company IDs
            try:
                company_ids = [int(id.strip()) for id in company_ids_param.split(',') if id.strip()]
                # Only filter by companies the user has access to
                accessible_company_ids = list(set(company_ids).intersection(set(user_company_ids)))
                if accessible_company_ids:
                    queryset = queryset.filter(company_id__in=accessible_company_ids)
            except (ValueError, TypeError):
                # If parsing fails, fall back to user's companies
                pass
        elif company_id:
            # Single company ID
            try:
                company_id_int = int(company_id)
                if company_id_int in user_company_ids:
                    queryset = queryset.filter(company_id=company_id_int)
            except (ValueError, TypeError):
                # If parsing fails, don't filter by company
                pass

        return queryset

    def get_serializer_class(self):
        """
        Usar diferentes serializers según la acción
        """
        if self.action == 'create':
            return ContactCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ContactUpdateSerializer
        elif self.action == 'list':
            return ContactListSerializer
        else:
            return ContactSerializer

    def perform_create(self, serializer):
        """
        Asignar la empresa al contacto basado en el contexto del usuario
        """
        # Obtener company_id del header o query params
        company_id = (
            self.request.headers.get('X-Company-ID') or
            self.request.query_params.get('company_id')
        )

        if company_id:
            # Verificar que el usuario tiene acceso a esta empresa
            has_access = UserRole.objects.filter(
                user=self.request.user,
                company_id=company_id,
                active=True
            ).exists()

            if not has_access:
                logger.warning(f"User {self.request.user.id} tried to create contact for company {company_id} without access")
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("No tienes permisos para crear contactos en esta empresa")

            from apps.companies.models import Company
            company = get_object_or_404(Company, id=company_id)
            serializer.save(company=company)
        else:
            # Si no se especifica empresa, usar la primera empresa del usuario
            user_companies = UserRole.objects.filter(
                user=self.request.user,
                active=True
            ).select_related('company')

            if not user_companies.exists():
                from rest_framework.exceptions import ValidationError
                raise ValidationError("Usuario no tiene acceso a ninguna empresa")

            serializer.save(company=user_companies.first().company)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Obtener estadísticas de contactos para las empresas del usuario
        """
        queryset = self.get_queryset()

        # Calcular estadísticas
        stats = queryset.aggregate(
            total_contacts=Count('id'),
            total_clients=Count('id', filter=Q(is_client=True)),
            total_providers=Count('id', filter=Q(is_provider=True)),
            dual_role_contacts=Count('id', filter=Q(is_client=True, is_provider=True)),
            active_contacts=Count('id', filter=Q(is_active=True)),
            inactive_contacts=Count('id', filter=Q(is_active=False))
        )

        # Estadísticas por categoría
        category_stats = queryset.exclude(
            category__isnull=True
        ).exclude(
            category__exact=''
        ).values('category').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        categories = {item['category']: item['count'] for item in category_stats}
        stats['categories'] = categories

        serializer = ContactStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def clients(self, request):
        """
        Obtener solo contactos que son clientes
        """
        queryset = self.get_queryset().filter(is_client=True)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = ContactListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ContactListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Obtener solo contactos que son proveedores
        """
        queryset = self.get_queryset().filter(is_provider=True)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = ContactListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ContactListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dual_role(self, request):
        """
        Obtener contactos que son tanto clientes como proveedores
        """
        queryset = self.get_queryset().filter(is_client=True, is_provider=True)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = ContactListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ContactListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search_by_rut(self, request):
        """
        Buscar contacto por RUT específico
        """
        rut = request.query_params.get('rut')
        if not rut:
            return Response(
                {'error': 'Parámetro "rut" requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Limpiar y formatear RUT para búsqueda
        clean_rut = rut.replace('.', '').replace('-', '')

        # Buscar por diferentes formatos posibles
        queryset = self.get_queryset().filter(
            Q(tax_id__icontains=clean_rut) |
            Q(tax_id__exact=rut) |
            Q(tax_id__icontains=rut)
        )

        if queryset.exists():
            serializer = ContactSerializer(queryset.first())
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'Contacto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def toggle_client(self, request, pk=None):
        """
        Alternar el estado de cliente del contacto
        """
        contact = self.get_object()
        contact.is_client = not contact.is_client

        # Asegurar que mantenga al menos un rol
        if not contact.is_client and not contact.is_provider:
            contact.is_provider = True

        contact.save()

        serializer = ContactSerializer(contact)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle_provider(self, request, pk=None):
        """
        Alternar el estado de proveedor del contacto
        """
        contact = self.get_object()
        contact.is_provider = not contact.is_provider

        # Asegurar que mantenga al menos un rol
        if not contact.is_client and not contact.is_provider:
            contact.is_client = True

        contact.save()

        serializer = ContactSerializer(contact)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """
        Alternar el estado activo/inactivo del contacto
        """
        contact = self.get_object()
        contact.is_active = not contact.is_active
        contact.save()

        serializer = ContactSerializer(contact)
        return Response(serializer.data)
