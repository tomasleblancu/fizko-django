from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel


class Employee(TimeStampedModel):
    """
    Model to store employee information
    """

    # Basic identification
    tax_id = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$',
            message='RUT must be in format XX.XXX.XXX-X'
        )],
        help_text="Employee RUT with format XX.XXX.XXX-X"
    )

    # Personal information
    first_name = models.CharField(max_length=100, help_text="Employee first name")
    last_name = models.CharField(max_length=100, help_text="Employee last name")
    email = models.EmailField(help_text="Employee email address")
    phone = models.CharField(max_length=20, blank=True, help_text="Phone number")
    mobile_phone = models.CharField(max_length=20, blank=True, help_text="Mobile phone number")

    # Address information
    address = models.CharField(max_length=255, blank=True, help_text="Employee address")
    city = models.CharField(max_length=100, blank=True, help_text="City")
    region = models.CharField(max_length=100, blank=True, help_text="Region")
    postal_code = models.CharField(max_length=10, blank=True, help_text="Postal code")

    # Personal details
    birth_date = models.DateField(null=True, blank=True, help_text="Date of birth")
    nationality = models.CharField(max_length=50, default='Chilean', help_text="Nationality")
    civil_status = models.CharField(
        max_length=20,
        choices=[
            ('SINGLE', 'Single'),
            ('MARRIED', 'Married'),
            ('DIVORCED', 'Divorced'),
            ('WIDOWED', 'Widowed'),
            ('SEPARATED', 'Separated'),
        ],
        default='SINGLE',
        help_text="Civil status"
    )

    # Employment status
    is_active = models.BooleanField(default=True, help_text="Is employee currently active")
    hire_date = models.DateField(help_text="Date when employee was hired")
    termination_date = models.DateField(null=True, blank=True, help_text="Date when employment ended")
    termination_reason = models.TextField(blank=True, help_text="Reason for termination")

    # Banking information
    bank_name = models.CharField(max_length=100, blank=True, help_text="Bank name for salary payments")
    bank_account_type = models.CharField(
        max_length=20,
        choices=[
            ('CHECKING', 'Checking Account'),
            ('SAVINGS', 'Savings Account'),
        ],
        blank=True,
        help_text="Type of bank account"
    )
    bank_account_number = models.CharField(max_length=50, blank=True, help_text="Bank account number")

    # Emergency contact
    emergency_contact_name = models.CharField(max_length=200, blank=True, help_text="Emergency contact name")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, help_text="Emergency contact phone")
    emergency_contact_relationship = models.CharField(max_length=50, blank=True, help_text="Relationship to employee")

    # Company relationship
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='employees',
        help_text="Company the employee works for"
    )

    class Meta:
        db_table = 'hr_employees'
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['last_name', 'first_name']
        unique_together = [
            ('tax_id', 'company'),  # Same RUT cannot exist twice in the same company
            ('email', 'company'),   # Same email cannot exist twice in the same company
        ]
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['tax_id']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.tax_id})"

    @property
    def full_name(self):
        """Returns the employee's full name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        """Calculates employee's age if birth_date is provided"""
        if self.birth_date:
            today = timezone.now().date()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None

    @property
    def years_of_service(self):
        """Calculates years of service"""
        end_date = self.termination_date or timezone.now().date()
        years = end_date.year - self.hire_date.year - ((end_date.month, end_date.day) < (self.hire_date.month, self.hire_date.day))
        return max(0, years)

    @property
    def current_contract(self):
        """Returns the current active contract"""
        return self.contracts.filter(is_active=True).first()


class EmployeeContract(TimeStampedModel):
    """
    Model to store employee contract information and employment terms
    """

    CONTRACT_TYPE_CHOICES = [
        ('INDEFINITE', 'Indefinite Term'),
        ('FIXED_TERM', 'Fixed Term'),
        ('PROJECT', 'Project-based'),
        ('TEMPORARY', 'Temporary'),
        ('INTERNSHIP', 'Internship'),
        ('PART_TIME', 'Part Time'),
    ]

    PAYMENT_FREQUENCY_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('BIWEEKLY', 'Bi-weekly'),
        ('WEEKLY', 'Weekly'),
        ('DAILY', 'Daily'),
        ('HOURLY', 'Hourly'),
    ]

    # Contract identification
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='contracts',
        help_text="Employee this contract belongs to"
    )

    contract_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique contract number"
    )

    # Contract details
    contract_type = models.CharField(
        max_length=20,
        choices=CONTRACT_TYPE_CHOICES,
        help_text="Type of employment contract"
    )

    start_date = models.DateField(help_text="Contract start date")
    end_date = models.DateField(null=True, blank=True, help_text="Contract end date (for fixed-term contracts)")

    # Job details
    job_title = models.CharField(max_length=200, help_text="Employee job title")
    department = models.CharField(max_length=100, blank=True, help_text="Department or area")
    reporting_manager = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        help_text="Direct manager/supervisor"
    )

    # Compensation
    base_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Base salary amount in CLP"
    )

    payment_frequency = models.CharField(
        max_length=20,
        choices=PAYMENT_FREQUENCY_CHOICES,
        default='MONTHLY',
        help_text="How often the employee is paid"
    )

    # Chilean-specific tax and social security information
    taxable_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Monthly taxable income (base imponible) in CLP"
    )

    # Work schedule
    weekly_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=45.00,
        help_text="Weekly working hours"
    )

    work_schedule = models.TextField(
        blank=True,
        help_text="Description of work schedule (e.g., Monday to Friday 9:00-18:00)"
    )

    # Benefits and allowances
    transportation_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly transportation allowance in CLP"
    )

    meal_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly meal allowance in CLP"
    )

    family_allowance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly family allowance in CLP"
    )

    other_allowances = models.JSONField(
        default=dict,
        blank=True,
        help_text="Other allowances and benefits"
    )

    # Chilean social security and health
    pension_system = models.CharField(
        max_length=20,
        choices=[
            ('AFP', 'AFP (Private Pension System)'),
            ('INP', 'INP (Public Pension System)'),
        ],
        default='AFP',
        help_text="Pension system"
    )

    afp_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="AFP name (if applicable)"
    )

    health_system = models.CharField(
        max_length=20,
        choices=[
            ('FONASA', 'FONASA (Public Health)'),
            ('ISAPRE', 'ISAPRE (Private Health)'),
        ],
        default='FONASA',
        help_text="Health system"
    )

    isapre_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="ISAPRE name (if applicable)"
    )

    health_plan_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly health plan value in CLP"
    )

    # Employment status
    is_active = models.BooleanField(default=True, help_text="Is this contract currently active")

    # Additional terms
    probation_period_months = models.IntegerField(
        default=3,
        help_text="Probation period in months"
    )

    vacation_days_per_year = models.IntegerField(
        default=15,
        help_text="Annual vacation days (legal minimum is 15 working days)"
    )

    notice_period_days = models.IntegerField(
        default=30,
        help_text="Notice period required for termination in days"
    )

    contract_notes = models.TextField(
        blank=True,
        help_text="Additional contract terms and notes"
    )

    class Meta:
        db_table = 'hr_employee_contracts'
        verbose_name = 'Employee Contract'
        verbose_name_plural = 'Employee Contracts'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'is_active']),
            models.Index(fields=['contract_type']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.employee.full_name} - {self.job_title} ({self.contract_number})"

    @property
    def is_current(self):
        """Checks if this contract is currently active based on dates"""
        today = timezone.now().date()
        if self.end_date:
            return self.start_date <= today <= self.end_date
        return self.start_date <= today

    @property
    def monthly_gross_salary(self):
        """Calculates monthly gross salary including allowances"""
        return self.base_salary + self.transportation_allowance + self.meal_allowance + self.family_allowance

    @property
    def contract_duration_months(self):
        """Calculates contract duration in months"""
        if self.end_date:
            months = (self.end_date.year - self.start_date.year) * 12 + (self.end_date.month - self.start_date.month)
            return max(1, months)
        return None

    def save(self, *args, **kwargs):
        """Override save to ensure only one active contract per employee"""
        if self.is_active:
            # Set all other contracts for this employee as inactive
            EmployeeContract.objects.filter(
                employee=self.employee,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)

        super().save(*args, **kwargs)
