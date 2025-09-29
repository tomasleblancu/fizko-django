from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, DecimalField, Case, When
from datetime import datetime, timedelta
import logging

from .models import Employee, EmployeeContract
from .serializers import (
    EmployeeSerializer, EmployeeCreateSerializer,
    EmployeeContractSerializer, EmployeeContractCreateSerializer,
    EmployeeSummarySerializer, PayrollSummarySerializer
)
from apps.core.permissions import IsCompanyMember
from apps.companies.models import Company

logger = logging.getLogger(__name__)


class EmployeeViewSet(viewsets.ModelViewSet):
    """ViewSet for employee management"""
    serializer_class = EmployeeSerializer

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only require authentication for write operations, company validation is done in the methods
            permission_classes = [IsAuthenticated]
        else:
            # For other actions (list, retrieve), require company membership
            permission_classes = [IsAuthenticated, IsCompanyMember]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Filter employees by company of the user"""
        return Employee.objects.select_related('company').prefetch_related('contracts').order_by('last_name', 'first_name')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return EmployeeCreateSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        """Create a new employee with company validation"""
        try:
            # Get company_id from request data
            company_id = request.data.get('company')
            if not company_id:
                return Response({
                    'error': 'Company ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate user has access to this company
            from apps.accounts.models import UserRole
            if not UserRole.objects.filter(
                user=request.user,
                company_id=company_id,
                active=True
            ).exists():
                return Response({
                    'error': 'You do not have permission to create employees for this company'
                }, status=status.HTTP_403_FORBIDDEN)

            # Proceed with normal creation
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error creating employee: {str(e)}")
            return Response({
                'error': 'Error creating employee',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        """Update an employee with company validation"""
        try:
            employee = self.get_object()

            # Validate user has access to this company
            from apps.accounts.models import UserRole
            if not UserRole.objects.filter(
                user=request.user,
                company_id=employee.company.id,
                active=True
            ).exists():
                return Response({
                    'error': 'You do not have permission to update employees from this company'
                }, status=status.HTTP_403_FORBIDDEN)

            # Proceed with normal update
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error updating employee: {str(e)}")
            return Response({
                'error': 'Error updating employee',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def partial_update(self, request, *args, **kwargs):
        """Partially update an employee with company validation"""
        try:
            employee = self.get_object()

            # Validate user has access to this company
            from apps.accounts.models import UserRole
            if not UserRole.objects.filter(
                user=request.user,
                company_id=employee.company.id,
                active=True
            ).exists():
                return Response({
                    'error': 'You do not have permission to update employees from this company'
                }, status=status.HTTP_403_FORBIDDEN)

            # Proceed with normal partial update
            return super().partial_update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error updating employee: {str(e)}")
            return Response({
                'error': 'Error updating employee',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        """Delete an employee with company validation"""
        try:
            employee = self.get_object()

            # Validate user has access to this company
            from apps.accounts.models import UserRole
            if not UserRole.objects.filter(
                user=request.user,
                company_id=employee.company.id,
                active=True
            ).exists():
                return Response({
                    'error': 'You do not have permission to delete employees from this company'
                }, status=status.HTTP_403_FORBIDDEN)

            # Proceed with normal deletion
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error deleting employee: {str(e)}")
            return Response({
                'error': 'Error deleting employee',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_companies(self, request):
        """Get and validate companies from request"""
        company_ids_param = request.query_params.get('company_ids')
        if company_ids_param:
            try:
                company_ids = [int(id.strip()) for id in company_ids_param.split(',') if id.strip()]
                if not company_ids:
                    raise ValueError("Array of company_ids is empty")

                companies = Company.objects.filter(id__in=company_ids)
                if companies.count() != len(company_ids):
                    found_ids = list(companies.values_list('id', flat=True))
                    missing_ids = set(company_ids) - set(found_ids)
                    raise ValueError(f"Companies not found: {missing_ids}")

                return list(companies)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Error parsing company_ids: {str(e)}")

        company_id = request.query_params.get('company_id')
        if not company_id:
            raise ValueError("company_id or company_ids parameter is required")

        try:
            company_id = int(company_id)
            company = Company.objects.get(id=company_id)
            return [company]
        except (ValueError, Company.DoesNotExist):
            raise ValueError(f"Company with ID {company_id} not found")

    def list(self, request):
        """
        List employees with filtering and search
        GET /api/v1/hr/employees/?company_id=1&is_active=true&search=john&department=IT
        """
        try:
            companies = self.get_companies(request)

            # Base queryset filtered by companies
            queryset = self.get_queryset().filter(company__in=companies)

            # Filters
            is_active = request.query_params.get('is_active')
            if is_active is not None:
                is_active_bool = is_active.lower() == 'true'
                queryset = queryset.filter(is_active=is_active_bool)

            search = request.query_params.get('search')
            if search:
                search_query = Q(
                    first_name__icontains=search
                ) | Q(
                    last_name__icontains=search
                ) | Q(
                    email__icontains=search
                ) | Q(
                    tax_id__icontains=search
                )
                queryset = queryset.filter(search_query)

            department = request.query_params.get('department')
            if department:
                # Filter by current contract department
                queryset = queryset.filter(
                    contracts__department__icontains=department,
                    contracts__is_active=True
                )

            job_title = request.query_params.get('job_title')
            if job_title:
                queryset = queryset.filter(
                    contracts__job_title__icontains=job_title,
                    contracts__is_active=True
                )

            # Ordering
            ordering = request.query_params.get('ordering', 'last_name')
            valid_fields = ['first_name', 'last_name', 'email', 'hire_date', 'tax_id']
            order_field = ordering.lstrip('-')
            if order_field in valid_fields:
                queryset = queryset.order_by(ordering)

            # Pagination
            page_size = int(request.query_params.get('page_size', 50))
            page = int(request.query_params.get('page', 1))

            total_count = queryset.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size

            employees = queryset[start_index:end_index]
            serializer = self.get_serializer(employees, many=True)

            has_next = end_index < total_count
            has_previous = page > 1

            return Response({
                'results': serializer.data,
                'count': total_count,
                'next': f'?page={page + 1}' if has_next else None,
                'previous': f'?page={page - 1}' if has_previous else None,
                'page': page,
                'page_size': page_size
            })

        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in employee list: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get employee summary statistics
        GET /api/v1/hr/employees/summary/?company_id=1
        """
        try:
            companies = self.get_companies(request)
            queryset = self.get_queryset().filter(company__in=companies)

            # Basic counts
            total_employees = queryset.count()
            active_employees = queryset.filter(is_active=True).count()
            inactive_employees = total_employees - active_employees

            # Department breakdown (from current contracts)
            department_stats = {}
            active_contracts = EmployeeContract.objects.filter(
                employee__company__in=companies,
                is_active=True
            ).values('department').annotate(count=Count('id'))

            for item in active_contracts:
                dept = item['department'] or 'No Department'
                department_stats[dept] = item['count']

            # Contract type breakdown
            contract_type_stats = {}
            contract_types = EmployeeContract.objects.filter(
                employee__company__in=companies,
                is_active=True
            ).values('contract_type').annotate(count=Count('id'))

            for item in contract_types:
                contract_type_stats[item['contract_type']] = item['count']

            # Average years of service
            active_employees_qs = queryset.filter(is_active=True)
            if active_employees_qs.exists():
                total_years = sum(emp.years_of_service for emp in active_employees_qs)
                avg_years = total_years / active_employees_qs.count()
            else:
                avg_years = 0

            # Total monthly payroll
            total_payroll = EmployeeContract.objects.filter(
                employee__company__in=companies,
                is_active=True
            ).aggregate(
                total=Sum('base_salary')
            )['total'] or 0

            summary_data = {
                'total_employees': total_employees,
                'active_employees': active_employees,
                'inactive_employees': inactive_employees,
                'employees_by_department': department_stats,
                'employees_by_contract_type': contract_type_stats,
                'average_years_of_service': round(avg_years, 2),
                'total_monthly_payroll': float(total_payroll)
            }

            serializer = EmployeeSummarySerializer(summary_data)
            return Response(serializer.data)

        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in employee summary: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmployeeContractViewSet(viewsets.ModelViewSet):
    """ViewSet for employee contract management"""
    serializer_class = EmployeeContractSerializer

    def get_permissions(self):
        """Return appropriate permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only require authentication for write operations, company validation is done in the methods
            permission_classes = [IsAuthenticated]
        else:
            # For other actions (list, retrieve), require company membership
            permission_classes = [IsAuthenticated, IsCompanyMember]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Filter contracts by company of the user"""
        return EmployeeContract.objects.select_related('employee', 'reporting_manager').order_by('-start_date')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return EmployeeContractCreateSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        """Create a new contract with company validation"""
        try:
            # Get employee from request data and validate company access
            employee_id = request.data.get('employee')
            if not employee_id:
                return Response({
                    'error': 'Employee ID is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get the employee and their company
            try:
                employee = Employee.objects.select_related('company').get(id=employee_id)
                company_id = employee.company.id
            except Employee.DoesNotExist:
                return Response({
                    'error': 'Employee not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Validate user has access to this company
            from apps.accounts.models import UserRole
            if not UserRole.objects.filter(
                user=request.user,
                company_id=company_id,
                active=True
            ).exists():
                return Response({
                    'error': 'You do not have permission to create contracts for this company'
                }, status=status.HTTP_403_FORBIDDEN)

            # Proceed with normal creation
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            return Response({
                'error': 'Error creating contract',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        """Delete a contract with company validation"""
        try:
            contract = self.get_object()

            # Validate user has access to this company (through employee)
            from apps.accounts.models import UserRole
            if not UserRole.objects.filter(
                user=request.user,
                company_id=contract.employee.company.id,
                active=True
            ).exists():
                return Response({
                    'error': 'You do not have permission to delete contracts from this company'
                }, status=status.HTTP_403_FORBIDDEN)

            # Proceed with normal deletion
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error deleting contract: {str(e)}")
            return Response({
                'error': 'Error deleting contract',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_companies(self, request):
        """Get and validate companies from request"""
        company_ids_param = request.query_params.get('company_ids')
        if company_ids_param:
            try:
                company_ids = [int(id.strip()) for id in company_ids_param.split(',') if id.strip()]
                companies = Company.objects.filter(id__in=company_ids)
                return list(companies)
            except (ValueError, TypeError):
                pass

        company_id = request.query_params.get('company_id')
        if company_id:
            try:
                company = Company.objects.get(id=int(company_id))
                return [company]
            except (ValueError, Company.DoesNotExist):
                pass

        raise ValueError("company_id or company_ids parameter is required")

    def list(self, request):
        """
        List employee contracts with filtering
        GET /api/v1/hr/contracts/?company_id=1&is_active=true&employee_id=5
        """
        try:
            companies = self.get_companies(request)

            # Base queryset filtered by companies
            queryset = self.get_queryset().filter(employee__company__in=companies)

            # Filters
            is_active = request.query_params.get('is_active')
            if is_active is not None:
                is_active_bool = is_active.lower() == 'true'
                queryset = queryset.filter(is_active=is_active_bool)

            employee_id = request.query_params.get('employee_id')
            if employee_id:
                try:
                    queryset = queryset.filter(employee_id=int(employee_id))
                except ValueError:
                    pass

            contract_type = request.query_params.get('contract_type')
            if contract_type:
                queryset = queryset.filter(contract_type=contract_type)

            department = request.query_params.get('department')
            if department:
                queryset = queryset.filter(department__icontains=department)

            # Date range filters
            start_date_from = request.query_params.get('start_date_from')
            if start_date_from:
                try:
                    start_date_dt = datetime.strptime(start_date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(start_date__gte=start_date_dt)
                except ValueError:
                    pass

            start_date_to = request.query_params.get('start_date_to')
            if start_date_to:
                try:
                    start_date_dt = datetime.strptime(start_date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(start_date__lte=start_date_dt)
                except ValueError:
                    pass

            # Pagination
            page_size = int(request.query_params.get('page_size', 50))
            page = int(request.query_params.get('page', 1))

            total_count = queryset.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size

            contracts = queryset[start_index:end_index]
            serializer = self.get_serializer(contracts, many=True)

            has_next = end_index < total_count
            has_previous = page > 1

            return Response({
                'results': serializer.data,
                'count': total_count,
                'next': f'?page={page + 1}' if has_next else None,
                'previous': f'?page={page - 1}' if has_previous else None,
                'page': page,
                'page_size': page_size
            })

        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in contract list: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def payroll_summary(self, request):
        """
        Get payroll summary for active contracts
        GET /api/v1/hr/contracts/payroll_summary/?company_id=1
        """
        try:
            companies = self.get_companies(request)

            # Get active contracts for the companies
            queryset = self.get_queryset().filter(
                employee__company__in=companies,
                is_active=True
            )

            # Calculate totals
            totals = queryset.aggregate(
                total_base_salary=Sum('base_salary'),
                total_transportation=Sum('transportation_allowance'),
                total_meal=Sum('meal_allowance'),
                total_family=Sum('family_allowance'),
                employee_count=Count('id')
            )

            # Handle None values from aggregations
            total_base_salary = totals['total_base_salary'] or 0
            total_transportation = totals['total_transportation'] or 0
            total_meal = totals['total_meal'] or 0
            total_family = totals['total_family'] or 0

            total_allowances = total_transportation + total_meal + total_family
            total_gross = total_base_salary + total_allowances

            avg_salary = (
                total_gross / totals['employee_count']
                if totals['employee_count'] > 0 else 0
            )

            # Payroll by department
            dept_payroll = {}
            dept_data = queryset.values('department').annotate(
                base_salary=Sum('base_salary'),
                transportation=Sum('transportation_allowance'),
                meal=Sum('meal_allowance'),
                family=Sum('family_allowance'),
                count=Count('id')
            )

            for item in dept_data:
                dept = item['department'] or 'No Department'
                base_sal = item['base_salary'] or 0
                transportation = item['transportation'] or 0
                meal = item['meal'] or 0
                family = item['family'] or 0
                allowances_total = transportation + meal + family

                dept_payroll[dept] = {
                    'base_salary': float(base_sal),
                    'allowances': float(allowances_total),
                    'total': float(base_sal + allowances_total),
                    'employee_count': item['count']
                }

            summary_data = {
                'total_base_salary': float(total_base_salary),
                'total_allowances': float(total_allowances),
                'total_gross_salary': float(total_gross),
                'employee_count': totals['employee_count'],
                'average_salary': float(avg_salary),
                'payroll_by_department': dept_payroll
            }

            serializer = PayrollSummarySerializer(summary_data)
            return Response(serializer.data)

        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in payroll summary: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
