from rest_framework import serializers
from .models import Employee, EmployeeContract


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for Employee model"""

    # Computed fields
    full_name = serializers.ReadOnlyField()
    age = serializers.ReadOnlyField()
    years_of_service = serializers.ReadOnlyField()
    current_contract = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'tax_id', 'first_name', 'last_name', 'full_name', 'email',
            'phone', 'mobile_phone', 'address', 'city', 'region', 'postal_code',
            'birth_date', 'age', 'nationality', 'civil_status',
            'is_active', 'hire_date', 'termination_date', 'termination_reason',
            'years_of_service', 'bank_name', 'bank_account_type', 'bank_account_number',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
            'company', 'current_contract', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'full_name', 'age', 'years_of_service']

    def get_current_contract(self, obj):
        """Get current active contract details"""
        current_contract = obj.current_contract
        if current_contract:
            return {
                'id': current_contract.id,
                'contract_number': current_contract.contract_number,
                'job_title': current_contract.job_title,
                'department': current_contract.department,
                'base_salary': float(current_contract.base_salary),
                'start_date': current_contract.start_date,
                'contract_type': current_contract.contract_type,
                'is_current': current_contract.is_current
            }
        return None

    def validate(self, data):
        """Custom validation for employee data during updates"""
        # For updates, we need to get the company either from data or from the instance
        company = data.get('company')
        if not company and self.instance:
            company = self.instance.company

        if not company:
            raise serializers.ValidationError("Company is required")

        # Check if RUT already exists for another employee in the same company
        tax_id = data.get('tax_id')
        if tax_id:
            existing_employee_query = Employee.objects.filter(
                tax_id=tax_id,
                company=company
            )
            # Exclude current instance if updating
            if self.instance:
                existing_employee_query = existing_employee_query.exclude(id=self.instance.id)

            existing_employee = existing_employee_query.first()
            if existing_employee:
                raise serializers.ValidationError({
                    'tax_id': f"An employee with this RUT already exists in {company.business_name}"
                })

        # Check if email already exists for another employee in the same company
        email = data.get('email')
        if email:
            existing_employee_query = Employee.objects.filter(
                email=email,
                company=company
            )
            # Exclude current instance if updating
            if self.instance:
                existing_employee_query = existing_employee_query.exclude(id=self.instance.id)

            existing_employee = existing_employee_query.first()
            if existing_employee:
                raise serializers.ValidationError({
                    'email': f"An employee with this email already exists in {company.business_name}"
                })

        return data


class EmployeeCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating employees"""

    class Meta:
        model = Employee
        fields = [
            'tax_id', 'first_name', 'last_name', 'email', 'phone', 'mobile_phone',
            'address', 'city', 'region', 'postal_code', 'birth_date', 'nationality',
            'civil_status', 'hire_date', 'bank_name', 'bank_account_type',
            'bank_account_number', 'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship', 'company'
        ]

    def validate(self, data):
        """Custom validation for employee data"""
        # Get the company from the data
        company = data.get('company')
        if not company:
            raise serializers.ValidationError("Company is required")

        # Check if RUT already exists for another employee in the same company
        tax_id = data.get('tax_id')
        if tax_id:
            existing_employee = Employee.objects.filter(
                tax_id=tax_id,
                company=company
            ).first()
            if existing_employee:
                raise serializers.ValidationError({
                    'tax_id': f"An employee with this RUT already exists in {company.business_name}"
                })

        # Check if email already exists for another employee in the same company
        email = data.get('email')
        if email:
            existing_employee = Employee.objects.filter(
                email=email,
                company=company
            ).first()
            if existing_employee:
                raise serializers.ValidationError({
                    'email': f"An employee with this email already exists in {company.business_name}"
                })

        return data


class EmployeeContractSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeContract model"""

    # Computed fields
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_tax_id = serializers.CharField(source='employee.tax_id', read_only=True)
    is_current = serializers.ReadOnlyField()
    monthly_gross_salary = serializers.ReadOnlyField()
    contract_duration_months = serializers.ReadOnlyField()
    reporting_manager_name = serializers.CharField(source='reporting_manager.full_name', read_only=True)

    class Meta:
        model = EmployeeContract
        fields = [
            'id', 'employee', 'employee_name', 'employee_tax_id', 'contract_number',
            'contract_type', 'start_date', 'end_date', 'job_title', 'department',
            'reporting_manager', 'reporting_manager_name', 'base_salary', 'payment_frequency',
            'taxable_income', 'weekly_hours', 'work_schedule', 'transportation_allowance',
            'meal_allowance', 'family_allowance', 'other_allowances', 'pension_system',
            'afp_name', 'health_system', 'isapre_name', 'health_plan_value',
            'is_active', 'is_current', 'monthly_gross_salary', 'contract_duration_months',
            'probation_period_months', 'vacation_days_per_year', 'notice_period_days',
            'contract_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'employee_name', 'employee_tax_id',
            'is_current', 'monthly_gross_salary', 'contract_duration_months',
            'reporting_manager_name'
        ]

    def validate_contract_number(self, value):
        """Validate unique contract number"""
        if EmployeeContract.objects.filter(contract_number=value).exists():
            raise serializers.ValidationError("A contract with this number already exists")
        return value

    def validate(self, data):
        """Custom validation for contract data"""
        # Validate date range for fixed-term contracts
        if data.get('contract_type') == 'FIXED_TERM' and not data.get('end_date'):
            raise serializers.ValidationError({
                'end_date': 'End date is required for fixed-term contracts'
            })

        # Validate end date is after start date
        if data.get('end_date') and data.get('start_date'):
            if data['end_date'] <= data['start_date']:
                raise serializers.ValidationError({
                    'end_date': 'End date must be after start date'
                })

        # Validate base salary is positive
        if data.get('base_salary') and data['base_salary'] <= 0:
            raise serializers.ValidationError({
                'base_salary': 'Base salary must be greater than zero'
            })

        # Validate taxable income
        if data.get('taxable_income') and data['taxable_income'] <= 0:
            raise serializers.ValidationError({
                'taxable_income': 'Taxable income must be greater than zero'
            })

        # Validate weekly hours
        if data.get('weekly_hours') and data['weekly_hours'] <= 0:
            raise serializers.ValidationError({
                'weekly_hours': 'Weekly hours must be greater than zero'
            })

        # Validate Chilean labor law compliance (maximum 45 hours per week for regular contracts)
        if data.get('weekly_hours') and data['weekly_hours'] > 45:
            if data.get('contract_type') not in ['PART_TIME', 'TEMPORARY']:
                raise serializers.ValidationError({
                    'weekly_hours': 'Weekly hours cannot exceed 45 for regular contracts (Chilean labor law)'
                })

        return data


class EmployeeContractCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating employee contracts"""

    class Meta:
        model = EmployeeContract
        fields = [
            'employee', 'contract_number', 'contract_type', 'start_date', 'end_date',
            'job_title', 'department', 'reporting_manager', 'base_salary',
            'payment_frequency', 'taxable_income', 'weekly_hours', 'work_schedule',
            'transportation_allowance', 'meal_allowance', 'family_allowance',
            'other_allowances', 'pension_system', 'afp_name', 'health_system',
            'isapre_name', 'health_plan_value', 'probation_period_months',
            'vacation_days_per_year', 'notice_period_days', 'contract_notes'
        ]

    def validate_contract_number(self, value):
        """Validate unique contract number"""
        if EmployeeContract.objects.filter(contract_number=value).exists():
            raise serializers.ValidationError("A contract with this number already exists")
        return value

    def validate(self, data):
        """Apply same validation as main serializer"""
        # Reuse validation logic from main serializer
        serializer = EmployeeContractSerializer()
        return serializer.validate(data)


class EmployeeSummarySerializer(serializers.Serializer):
    """Serializer for employee summary statistics"""

    total_employees = serializers.IntegerField()
    active_employees = serializers.IntegerField()
    inactive_employees = serializers.IntegerField()
    employees_by_department = serializers.DictField(child=serializers.IntegerField())
    employees_by_contract_type = serializers.DictField(child=serializers.IntegerField())
    average_years_of_service = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_monthly_payroll = serializers.DecimalField(max_digits=15, decimal_places=2)


class PayrollSummarySerializer(serializers.Serializer):
    """Serializer for payroll summary statistics"""

    total_base_salary = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_allowances = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_gross_salary = serializers.DecimalField(max_digits=15, decimal_places=2)
    employee_count = serializers.IntegerField()
    average_salary = serializers.DecimalField(max_digits=12, decimal_places=2)
    payroll_by_department = serializers.DictField(
        child=serializers.DictField(child=serializers.DecimalField(max_digits=15, decimal_places=2))
    )