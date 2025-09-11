from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import TimeStampedModel


class User(AbstractUser):
    """
    Modelo de usuario personalizado
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        
    def __str__(self):
        return self.email


class UserProfile(TimeStampedModel):
    """
    Perfil extendido del usuario
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    position = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
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