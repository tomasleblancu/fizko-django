from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import EmailValidator
from django.utils import timezone
from apps.core.models import TimeStampedModel
import uuid


class UserManager(BaseUserManager):
    """
    Manager personalizado para el modelo User que usa email como username
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es requerido')
        
        email = self.normalize_email(email)
        # Generar username basado en email si no se proporciona
        username = extra_fields.get('username', email.split('@')[0])
        extra_fields.setdefault('username', username)
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Modelo de usuario personalizado
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=False, help_text="Número completo con prefijo país sin +. Ej: 56912345678")
    is_verified = models.BooleanField(default=False)  # Legacy field - True only when both email and phone are verified
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Solo email es requerido para crear usuario
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        
    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override save to update is_verified based on email_verified and phone_verified"""
        self.is_verified = self.email_verified and self.phone_verified
        super().save(*args, **kwargs)

    @property
    def is_fully_verified(self):
        """Check if both email and phone are verified"""
        return self.email_verified and self.phone_verified


class UserProfile(TimeStampedModel):
    """
    Perfil extendido del usuario
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    position = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Campos para tracking del onboarding
    onboarding_completed = models.BooleanField(default=False)
    onboarding_step = models.IntegerField(default=1)
    skip_onboarding = models.BooleanField(default=False)  # Para usuarios invitados

    # Preferencias
    preferred_language = models.CharField(max_length=10, default='es')
    timezone = models.CharField(max_length=50, default='America/Santiago')

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.email} Profile"


class Role(TimeStampedModel):
    """
    Roles del sistema
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'roles'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        
    def __str__(self):
        return self.name


class UserRole(TimeStampedModel):
    """
    Relación usuario-empresa-rol
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_roles'
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        unique_together = ['user', 'company', 'role']
        
    def __str__(self):
        return f"{self.user.email} - {self.role.name} at {self.company.name}"


class VerificationCode(TimeStampedModel):
    """
    Códigos de verificación para email y teléfono
    """
    VERIFICATION_TYPES = [
        ('email', 'Email'),
        ('phone', 'Phone'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_codes')
    verification_type = models.CharField(max_length=10, choices=VERIFICATION_TYPES)
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    last_resent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'verification_codes'
        verbose_name = 'Verification Code'
        verbose_name_plural = 'Verification Codes'
        # Removed unique_together to allow multiple codes per user/type
        indexes = [
            models.Index(fields=['user', 'verification_type', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.verification_type} - {self.code}"

    @property
    def is_expired(self):
        """Check if the code has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if the code is valid (not used, not expired)"""
        return not self.is_used and not self.is_expired

    def mark_as_used(self):
        """Mark the code as used"""
        self.is_used = True
        self.save(update_fields=['is_used'])

    @classmethod
    def generate_code(cls):
        """Generate a random 6-digit verification code"""
        import random
        return f"{random.randint(100000, 999999)}"

    @classmethod
    def create_verification_code(cls, user, verification_type):
        """Create a new verification code for user"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db import transaction

        with transaction.atomic():
            # Deactivate existing codes for this user and type
            cls.objects.filter(
                user=user,
                verification_type=verification_type,
                is_used=False
            ).update(is_used=True)

            # Create new code
            code = cls.generate_code()
            expires_at = timezone.now() + timedelta(minutes=15)  # Code expires in 15 minutes

            return cls.objects.create(
                user=user,
                verification_type=verification_type,
                code=code,
                expires_at=expires_at
            )

    def can_resend(self):
        """Check if code can be resent (5 minute cooldown)"""
        if not self.last_resent_at:
            return True

        from django.utils import timezone
        from datetime import timedelta

        return timezone.now() > self.last_resent_at + timedelta(minutes=5)


class TeamInvitation(TimeStampedModel):
    """
    Invitaciones pendientes para unirse a equipos
    Ahora soporta invitaciones a múltiples empresas
    """

    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('expired', 'Expirada'),
        ('cancelled', 'Cancelada'),
    ]

    # Información de la invitación
    email = models.EmailField(validators=[EmailValidator()])
    companies = models.ManyToManyField('companies.Company', related_name='team_invitations')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    # Usuario que envía la invitación (debe ser owner)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')

    # Estado y tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Timestamps adicionales
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    # Usuario que acepta la invitación (se llena cuando se registra)
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_invitations'
    )

    class Meta:
        db_table = 'team_invitations'
        verbose_name = 'Team Invitation'
        verbose_name_plural = 'Team Invitations'
        # Ahora unique_together solo considera email y status ya que puede haber múltiples empresas
        # Un email no puede tener múltiples invitaciones activas con el mismo estado
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['token']),
            models.Index(fields=['expires_at', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'status'],
                condition=models.Q(status='pending'),
                name='unique_pending_invitation_per_email'
            ),
        ]

    def __str__(self):
        # Evitar problemas con instancias no guardadas
        if self.pk is None:
            return f"Invitation: {self.email} (unsaved)"

        try:
            company_names = ", ".join([
                company.display_name if hasattr(company, 'display_name') and company.display_name
                else company.business_name
                for company in self.companies.all()
            ])
            if not company_names:
                company_names = "No companies"
            role_name = self.role.name if self.role else "No role"
            return f"Invitation: {self.email} to {company_names} as {role_name}"
        except Exception:
            # Fallback en caso de errores
            return f"Invitation: {self.email} (ID: {self.pk})"

    def is_expired(self):
        """Verifica si la invitación ha expirado"""
        return timezone.now() > self.expires_at and self.status == 'pending'

    def can_be_accepted(self):
        """Verifica si la invitación puede ser aceptada"""
        return self.status == 'pending' and not self.is_expired()

    def mark_as_expired(self):
        """Marca la invitación como expirada"""
        self.status = 'expired'
        self.save(update_fields=['status'])

    def accept(self, user):
        """Acepta la invitación y crea UserRole para todas las empresas asociadas"""
        from datetime import datetime

        if not self.can_be_accepted():
            raise ValueError("Esta invitación no puede ser aceptada")

        created_roles = []
        companies_info = []

        # Crear UserRole para cada empresa asociada
        for company in self.companies.all():
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                company=company,
                defaults={'role': self.role, 'active': True}
            )
            if created:
                created_roles.append(user_role)

            # Recopilar información de la empresa
            companies_info.append({
                'id': company.id,
                'name': company.display_name if hasattr(company, 'display_name') and company.display_name
                       else company.business_name,
                'business_name': company.business_name,
                'tax_id': company.tax_id if hasattr(company, 'tax_id') else None,
                'role_created': created,
                'role': self.role.name
            })

        # Marcar invitación como aceptada
        self.status = 'accepted'
        self.accepted_by = user
        self.accepted_at = timezone.now()
        self.save()

        return {
            'user_roles': created_roles,
            'companies': companies_info,
            'role': {
                'id': self.role.id,
                'name': self.role.name,
                'description': self.role.description
            },
            'total_companies': len(companies_info),
            'new_roles_created': len(created_roles)
        }

    def get_companies(self):
        """Método helper para obtener todas las empresas asociadas"""
        return self.companies.all()

    def get_company_names(self):
        """Método helper para obtener los nombres de todas las empresas"""
        return [company.display_name if hasattr(company, 'display_name') and company.display_name
                else company.business_name for company in self.companies.all()]

    def has_company(self, company):
        """Verifica si la invitación incluye una empresa específica"""
        return self.companies.filter(id=company.id).exists()

    def save(self, *args, **kwargs):
        # Establecer fecha de expiración si no está definida (7 días por defecto)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)

        super().save(*args, **kwargs)


class PreLaunchSubscriber(TimeStampedModel):
    """
    Suscriptores del pre-lanzamiento de Fizko
    """
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="Email del suscriptor interesado en el pre-lanzamiento"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Dirección IP desde donde se registró"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent del navegador"
    )
    source = models.CharField(
        max_length=100,
        default='web',
        help_text="Fuente de la suscripción (web, mobile, etc.)"
    )
    notified = models.BooleanField(
        default=False,
        help_text="Indica si ya se le notificó del lanzamiento"
    )
    notified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que se le notificó del lanzamiento"
    )
    converted_to_user = models.BooleanField(
        default=False,
        help_text="Indica si el suscriptor se convirtió en usuario registrado"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pre_launch_subscription',
        help_text="Usuario creado a partir de este suscriptor"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notas adicionales sobre el suscriptor"
    )

    class Meta:
        db_table = 'pre_launch_subscribers'
        verbose_name = 'Pre-Launch Subscriber'
        verbose_name_plural = 'Pre-Launch Subscribers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
            models.Index(fields=['notified', 'converted_to_user']),
        ]

    def __str__(self):
        status = []
        if self.notified:
            status.append("Notificado")
        if self.converted_to_user:
            status.append("Convertido")
        status_str = f" ({', '.join(status)})" if status else ""
        return f"{self.email}{status_str}"

    def mark_as_notified(self):
        """Marca el suscriptor como notificado"""
        self.notified = True
        self.notified_at = timezone.now()
        self.save(update_fields=['notified', 'notified_at'])

    def mark_as_converted(self, user):
        """Marca el suscriptor como convertido a usuario"""
        self.converted_to_user = True
        self.user = user
        self.save(update_fields=['converted_to_user', 'user'])